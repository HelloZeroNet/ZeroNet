import time
import os
import subprocess
import shutil
import collections
import math
import warnings
import base64
import binascii
import json

import gevent
import gevent.lock

from Plugin import PluginManager
from Debug import Debug
from Crypt import CryptHash
with warnings.catch_warnings():
    warnings.filterwarnings("ignore")  # Ignore missing sha3 warning
    import merkletools

from util import helper
from util import Msgpack
import util
from .BigfilePiecefield import BigfilePiecefield, BigfilePiecefieldPacked


# We can only import plugin host clases after the plugins are loaded
@PluginManager.afterLoad
def importPluginnedClasses():
    global VerifyError, config
    from Content.ContentManager import VerifyError
    from Config import config

if "upload_nonces" not in locals():
    upload_nonces = {}


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def isCorsAllowed(self, path):
        if path == "/ZeroNet-Internal/BigfileUpload":
            return True
        else:
            return super(UiRequestPlugin, self).isCorsAllowed(path)

    @helper.encodeResponse
    def actionBigfileUpload(self):
        nonce = self.get.get("upload_nonce")
        if nonce not in upload_nonces:
            return self.error403("Upload nonce error.")

        upload_info = upload_nonces[nonce]
        del upload_nonces[nonce]

        self.sendHeader(200, "text/html", noscript=True, extra_headers={
            "Access-Control-Allow-Origin": "null",
            "Access-Control-Allow-Credentials": "true"
        })

        self.readMultipartHeaders(self.env['wsgi.input'])  # Skip http headers

        site = upload_info["site"]
        inner_path = upload_info["inner_path"]

        with site.storage.open(inner_path, "wb", create_dirs=True) as out_file:
            merkle_root, piece_size, piecemap_info = site.content_manager.hashBigfile(
                self.env['wsgi.input'], upload_info["size"], upload_info["piece_size"], out_file
            )

        if len(piecemap_info["sha512_pieces"]) == 1:  # Small file, don't split
            hash = binascii.hexlify(piecemap_info["sha512_pieces"][0])
            hash_id = site.content_manager.hashfield.getHashId(hash)
            site.content_manager.optionalDownloaded(inner_path, hash_id, upload_info["size"], own=True)

        else:  # Big file
            file_name = helper.getFilename(inner_path)
            site.storage.open(upload_info["piecemap"], "wb").write(Msgpack.pack({file_name: piecemap_info}))

            # Find piecemap and file relative path to content.json
            file_info = site.content_manager.getFileInfo(inner_path, new_file=True)
            content_inner_path_dir = helper.getDirname(file_info["content_inner_path"])
            piecemap_relative_path = upload_info["piecemap"][len(content_inner_path_dir):]
            file_relative_path = inner_path[len(content_inner_path_dir):]

            # Add file to content.json
            if site.storage.isFile(file_info["content_inner_path"]):
                content = site.storage.loadJson(file_info["content_inner_path"])
            else:
                content = {}
            if "files_optional" not in content:
                content["files_optional"] = {}

            content["files_optional"][file_relative_path] = {
                "sha512": merkle_root,
                "size": upload_info["size"],
                "piecemap": piecemap_relative_path,
                "piece_size": piece_size
            }

            merkle_root_hash_id = site.content_manager.hashfield.getHashId(merkle_root)
            site.content_manager.optionalDownloaded(inner_path, merkle_root_hash_id, upload_info["size"], own=True)
            site.storage.writeJson(file_info["content_inner_path"], content)

            site.content_manager.contents.loadItem(file_info["content_inner_path"])  # reload cache

        return json.dumps({
            "merkle_root": merkle_root,
            "piece_num": len(piecemap_info["sha512_pieces"]),
            "piece_size": piece_size,
            "inner_path": inner_path
        })

    def readMultipartHeaders(self, wsgi_input):
        found = False
        for i in range(100):
            line = wsgi_input.readline()
            if line == b"\r\n":
                found = True
                break
        if not found:
            raise Exception("No multipart header found")
        return i

    def actionFile(self, file_path, *args, **kwargs):
        if kwargs.get("file_size", 0) > 1024 * 1024 and kwargs.get("path_parts"):  # Only check files larger than 1MB
            path_parts = kwargs["path_parts"]
            site = self.server.site_manager.get(path_parts["address"])
            big_file = site.storage.openBigfile(path_parts["inner_path"], prebuffer=2 * 1024 * 1024)
            if big_file:
                kwargs["file_obj"] = big_file
                kwargs["file_size"] = big_file.size

        return super(UiRequestPlugin, self).actionFile(file_path, *args, **kwargs)


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def actionBigfileUploadInit(self, to, inner_path, size):
        valid_signers = self.site.content_manager.getValidSigners(inner_path)
        auth_address = self.user.getAuthAddress(self.site.address)
        if not self.site.settings["own"] and auth_address not in valid_signers:
            self.log.error("FileWrite forbidden %s not in valid_signers %s" % (auth_address, valid_signers))
            return self.response(to, {"error": "Forbidden, you can only modify your own files"})

        nonce = CryptHash.random()
        piece_size = 1024 * 1024
        inner_path = self.site.content_manager.sanitizePath(inner_path)
        file_info = self.site.content_manager.getFileInfo(inner_path, new_file=True)

        content_inner_path_dir = helper.getDirname(file_info["content_inner_path"])
        file_relative_path = inner_path[len(content_inner_path_dir):]

        upload_nonces[nonce] = {
            "added": time.time(),
            "site": self.site,
            "inner_path": inner_path,
            "websocket_client": self,
            "size": size,
            "piece_size": piece_size,
            "piecemap": inner_path + ".piecemap.msgpack"
        }
        return {
            "url": "/ZeroNet-Internal/BigfileUpload?upload_nonce=" + nonce,
            "piece_size": piece_size,
            "inner_path": inner_path,
            "file_relative_path": file_relative_path
        }

    def actionSiteSetAutodownloadBigfileLimit(self, to, limit):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        self.site.settings["autodownload_bigfile_size_limit"] = int(limit)
        self.response(to, "ok")

    def actionFileDelete(self, to, inner_path):
        piecemap_inner_path = inner_path + ".piecemap.msgpack"
        if self.hasFilePermission(inner_path) and self.site.storage.isFile(piecemap_inner_path):
            # Also delete .piecemap.msgpack file if exists
            self.log.debug("Deleting piecemap: %s" % piecemap_inner_path)
            file_info = self.site.content_manager.getFileInfo(piecemap_inner_path)
            if file_info:
                content_json = self.site.storage.loadJson(file_info["content_inner_path"])
                relative_path = file_info["relative_path"]
                if relative_path in content_json.get("files_optional", {}):
                    del content_json["files_optional"][relative_path]
                    self.site.storage.writeJson(file_info["content_inner_path"], content_json)
                    self.site.content_manager.loadContent(file_info["content_inner_path"], add_bad_files=False, force=True)
                    try:
                        self.site.storage.delete(piecemap_inner_path)
                    except Exception as err:
                        self.log.error("File %s delete error: %s" % (piecemap_inner_path, err))

        return super(UiWebsocketPlugin, self).actionFileDelete(to, inner_path)


@PluginManager.registerTo("ContentManager")
class ContentManagerPlugin(object):
    def getFileInfo(self, inner_path, *args, **kwargs):
        if "|" not in inner_path:
            return super(ContentManagerPlugin, self).getFileInfo(inner_path, *args, **kwargs)

        inner_path, file_range = inner_path.split("|")
        pos_from, pos_to = map(int, file_range.split("-"))
        file_info = super(ContentManagerPlugin, self).getFileInfo(inner_path, *args, **kwargs)
        return file_info

    def readFile(self, file_in, size, buff_size=1024 * 64):
        part_num = 0
        recv_left = size

        while 1:
            part_num += 1
            read_size = min(buff_size, recv_left)
            part = file_in.read(read_size)

            if not part:
                break
            yield part

            if part_num % 100 == 0:  # Avoid blocking ZeroNet execution during upload
                time.sleep(0.001)

            recv_left -= read_size
            if recv_left <= 0:
                break

    def hashBigfile(self, file_in, size, piece_size=1024 * 1024, file_out=None):
        self.site.settings["has_bigfile"] = True

        recv = 0
        try:
            piece_hash = CryptHash.sha512t()
            piece_hashes = []
            piece_recv = 0

            mt = merkletools.MerkleTools()
            mt.hash_function = CryptHash.sha512t

            part = ""
            for part in self.readFile(file_in, size):
                if file_out:
                    file_out.write(part)

                recv += len(part)
                piece_recv += len(part)
                piece_hash.update(part)
                if piece_recv >= piece_size:
                    piece_digest = piece_hash.digest()
                    piece_hashes.append(piece_digest)
                    mt.leaves.append(piece_digest)
                    piece_hash = CryptHash.sha512t()
                    piece_recv = 0

                    if len(piece_hashes) % 100 == 0 or recv == size:
                        self.log.info("- [HASHING:%.0f%%] Pieces: %s, %.1fMB/%.1fMB" % (
                            float(recv) / size * 100, len(piece_hashes), recv / 1024 / 1024, size / 1024 / 1024
                        ))
                        part = ""
            if len(part) > 0:
                piece_digest = piece_hash.digest()
                piece_hashes.append(piece_digest)
                mt.leaves.append(piece_digest)
        except Exception as err:
            raise err
        finally:
            if file_out:
                file_out.close()

        mt.make_tree()
        merkle_root = mt.get_merkle_root()
        if type(merkle_root) is bytes:  # Python <3.5
            merkle_root = merkle_root.decode()
        return merkle_root, piece_size, {
            "sha512_pieces": piece_hashes
        }

    def hashFile(self, dir_inner_path, file_relative_path, optional=False):
        inner_path = dir_inner_path + file_relative_path

        file_size = self.site.storage.getSize(inner_path)
        # Only care about optional files >1MB
        if not optional or file_size < 1 * 1024 * 1024:
            return super(ContentManagerPlugin, self).hashFile(dir_inner_path, file_relative_path, optional)

        back = {}
        content = self.contents.get(dir_inner_path + "content.json")

        hash = None
        piecemap_relative_path = None
        piece_size = None

        # Don't re-hash if it's already in content.json
        if content and file_relative_path in content.get("files_optional", {}):
            file_node = content["files_optional"][file_relative_path]
            if file_node["size"] == file_size:
                self.log.info("- [SAME SIZE] %s" % file_relative_path)
                hash = file_node.get("sha512")
                piecemap_relative_path = file_node.get("piecemap")
                piece_size = file_node.get("piece_size")

        if not hash or not piecemap_relative_path:  # Not in content.json yet
            if file_size < 5 * 1024 * 1024:  # Don't create piecemap automatically for files smaller than 5MB
                return super(ContentManagerPlugin, self).hashFile(dir_inner_path, file_relative_path, optional)

            self.log.info("- [HASHING] %s" % file_relative_path)
            merkle_root, piece_size, piecemap_info = self.hashBigfile(self.site.storage.open(inner_path, "rb"), file_size)
            if not hash:
                hash = merkle_root

            if not piecemap_relative_path:
                file_name = helper.getFilename(file_relative_path)
                piecemap_relative_path = file_relative_path + ".piecemap.msgpack"
                piecemap_inner_path = inner_path + ".piecemap.msgpack"

                self.site.storage.open(piecemap_inner_path, "wb").write(Msgpack.pack({file_name: piecemap_info}))

                back.update(super(ContentManagerPlugin, self).hashFile(dir_inner_path, piecemap_relative_path, optional=True))

        piece_num = int(math.ceil(float(file_size) / piece_size))

        # Add the merkle root to hashfield
        hash_id = self.site.content_manager.hashfield.getHashId(hash)
        self.optionalDownloaded(inner_path, hash_id, file_size, own=True)
        self.site.storage.piecefields[hash].frombytes(b"\x01" * piece_num)

        back[file_relative_path] = {"sha512": hash, "size": file_size, "piecemap": piecemap_relative_path, "piece_size": piece_size}
        return back

    def getPiecemap(self, inner_path):
        file_info = self.site.content_manager.getFileInfo(inner_path)
        piecemap_inner_path = helper.getDirname(file_info["content_inner_path"]) + file_info["piecemap"]
        self.site.needFile(piecemap_inner_path, priority=20)
        piecemap = Msgpack.unpack(self.site.storage.open(piecemap_inner_path, "rb").read())[helper.getFilename(inner_path)]
        piecemap["piece_size"] = file_info["piece_size"]
        return piecemap

    def verifyPiece(self, inner_path, pos, piece):
        piecemap = self.getPiecemap(inner_path)
        piece_i = int(pos / piecemap["piece_size"])
        if CryptHash.sha512sum(piece, format="digest") != piecemap["sha512_pieces"][piece_i]:
            raise VerifyError("Invalid hash")
        return True

    def verifyFile(self, inner_path, file, ignore_same=True):
        if "|" not in inner_path:
            return super(ContentManagerPlugin, self).verifyFile(inner_path, file, ignore_same)

        inner_path, file_range = inner_path.split("|")
        pos_from, pos_to = map(int, file_range.split("-"))

        return self.verifyPiece(inner_path, pos_from, file)

    def optionalDownloaded(self, inner_path, hash_id, size=None, own=False):
        if "|" in inner_path:
            inner_path, file_range = inner_path.split("|")
            pos_from, pos_to = map(int, file_range.split("-"))
            file_info = self.getFileInfo(inner_path)

            # Mark piece downloaded
            piece_i = int(pos_from / file_info["piece_size"])
            self.site.storage.piecefields[file_info["sha512"]][piece_i] = b"\x01"

            # Only add to site size on first request
            if hash_id in self.hashfield:
                size = 0
        elif size > 1024 * 1024:
            file_info = self.getFileInfo(inner_path)
            if file_info and "sha512" in file_info:  # We already have the file, but not in piecefield
                sha512 = file_info["sha512"]
                if sha512 not in self.site.storage.piecefields:
                    self.site.storage.checkBigfile(inner_path)

        return super(ContentManagerPlugin, self).optionalDownloaded(inner_path, hash_id, size, own)

    def optionalRemoved(self, inner_path, hash_id, size=None):
        if size and size > 1024 * 1024:
            file_info = self.getFileInfo(inner_path)
            sha512 = file_info["sha512"]
            if sha512 in self.site.storage.piecefields:
                del self.site.storage.piecefields[sha512]

            # Also remove other pieces of the file from download queue
            for key in list(self.site.bad_files.keys()):
                if key.startswith(inner_path + "|"):
                    del self.site.bad_files[key]
            self.site.worker_manager.removeSolvedFileTasks()
        return super(ContentManagerPlugin, self).optionalRemoved(inner_path, hash_id, size)


@PluginManager.registerTo("SiteStorage")
class SiteStoragePlugin(object):
    def __init__(self, *args, **kwargs):
        super(SiteStoragePlugin, self).__init__(*args, **kwargs)
        self.piecefields = collections.defaultdict(BigfilePiecefield)
        if "piecefields" in self.site.settings.get("cache", {}):
            for sha512, piecefield_packed in self.site.settings["cache"].get("piecefields").items():
                if piecefield_packed:
                    self.piecefields[sha512].unpack(base64.b64decode(piecefield_packed))
            self.site.settings["cache"]["piecefields"] = {}

    def createSparseFile(self, inner_path, size, sha512=None):
        file_path = self.getPath(inner_path)

        file_dir = os.path.dirname(file_path)
        if not os.path.isdir(file_dir):
            os.makedirs(file_dir)

        f = open(file_path, 'wb')
        f.truncate(min(1024 * 1024 * 5, size))  # Only pre-allocate up to 5MB
        f.close()
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.call(["fsutil", "sparse", "setflag", file_path], close_fds=True, startupinfo=startupinfo)

        if sha512 and sha512 in self.piecefields:
            self.log.debug("%s: File not exists, but has piecefield. Deleting piecefield." % inner_path)
            del self.piecefields[sha512]

    def write(self, inner_path, content):
        if "|" not in inner_path:
            return super(SiteStoragePlugin, self).write(inner_path, content)

        # Write to specific position by passing |{pos} after the filename
        inner_path, file_range = inner_path.split("|")
        pos_from, pos_to = map(int, file_range.split("-"))
        file_path = self.getPath(inner_path)

        # Create dir if not exist
        file_dir = os.path.dirname(file_path)
        if not os.path.isdir(file_dir):
            os.makedirs(file_dir)

        if not os.path.isfile(file_path):
            file_info = self.site.content_manager.getFileInfo(inner_path)
            self.createSparseFile(inner_path, file_info["size"])

        # Write file
        with open(file_path, "rb+") as file:
            file.seek(pos_from)
            if hasattr(content, 'read'):  # File-like object
                shutil.copyfileobj(content, file)  # Write buff to disk
            else:  # Simple string
                file.write(content)
        del content
        self.onUpdated(inner_path)

    def checkBigfile(self, inner_path):
        file_info = self.site.content_manager.getFileInfo(inner_path)
        if not file_info or (file_info and "piecemap" not in file_info):  # It's not a big file
            return False

        self.site.settings["has_bigfile"] = True
        file_path = self.getPath(inner_path)
        sha512 = file_info["sha512"]
        piece_num = int(math.ceil(float(file_info["size"]) / file_info["piece_size"]))
        if os.path.isfile(file_path):
            if sha512 not in self.piecefields:
                if open(file_path, "rb").read(128) == b"\0" * 128:
                    piece_data = b"\x00"
                else:
                    piece_data = b"\x01"
                self.log.debug("%s: File exists, but not in piecefield. Filling piecefiled with %s * %s." % (inner_path, piece_num, piece_data))
                self.piecefields[sha512].frombytes(piece_data * piece_num)
        else:
            self.log.debug("Creating bigfile: %s" % inner_path)
            self.createSparseFile(inner_path, file_info["size"], sha512)
            self.piecefields[sha512].frombytes(b"\x00" * piece_num)
            self.log.debug("Created bigfile: %s" % inner_path)
        return True

    def openBigfile(self, inner_path, prebuffer=0):
        if not self.checkBigfile(inner_path):
            return False
        self.site.needFile(inner_path, blocking=False)  # Download piecemap
        return BigFile(self.site, inner_path, prebuffer=prebuffer)


class BigFile(object):
    def __init__(self, site, inner_path, prebuffer=0):
        self.site = site
        self.inner_path = inner_path
        file_path = site.storage.getPath(inner_path)
        file_info = self.site.content_manager.getFileInfo(inner_path)
        self.piece_size = file_info["piece_size"]
        self.sha512 = file_info["sha512"]
        self.size = file_info["size"]
        self.prebuffer = prebuffer
        self.read_bytes = 0

        self.piecefield = self.site.storage.piecefields[self.sha512]
        self.f = open(file_path, "rb+")
        self.read_lock = gevent.lock.Semaphore()

    def read(self, buff=64 * 1024):
        with self.read_lock:
            pos = self.f.tell()
            read_until = min(self.size, pos + buff)
            requests = []
            # Request all required blocks
            while 1:
                piece_i = int(pos / self.piece_size)
                if piece_i * self.piece_size >= read_until:
                    break
                pos_from = piece_i * self.piece_size
                pos_to = pos_from + self.piece_size
                if not self.piecefield[piece_i]:
                    requests.append(self.site.needFile("%s|%s-%s" % (self.inner_path, pos_from, pos_to), blocking=False, update=True, priority=10))
                pos += self.piece_size

            if not all(requests):
                return None

            # Request prebuffer
            if self.prebuffer:
                prebuffer_until = min(self.size, read_until + self.prebuffer)
                priority = 3
                while 1:
                    piece_i = int(pos / self.piece_size)
                    if piece_i * self.piece_size >= prebuffer_until:
                        break
                    pos_from = piece_i * self.piece_size
                    pos_to = pos_from + self.piece_size
                    if not self.piecefield[piece_i]:
                        self.site.needFile("%s|%s-%s" % (self.inner_path, pos_from, pos_to), blocking=False, update=True, priority=max(0, priority))
                    priority -= 1
                    pos += self.piece_size

            gevent.joinall(requests)
            self.read_bytes += buff

            # Increase buffer for long reads
            if self.read_bytes > 7 * 1024 * 1024 and self.prebuffer < 5 * 1024 * 1024:
                self.site.log.debug("%s: Increasing bigfile buffer size to 5MB..." % self.inner_path)
                self.prebuffer = 5 * 1024 * 1024

            return self.f.read(buff)

    def seek(self, pos, whence=0):
        with self.read_lock:
            if whence == 2:  # Relative from file end
                pos = self.size + pos  # Use the real size instead of size on the disk
                whence = 0
            return self.f.seek(pos, whence)

    def tell(self):
        return self.f.tell()

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


@PluginManager.registerTo("WorkerManager")
class WorkerManagerPlugin(object):
    def addTask(self, inner_path, *args, **kwargs):
        file_info = kwargs.get("file_info")
        if file_info and "piecemap" in file_info:  # Bigfile
            self.site.settings["has_bigfile"] = True

            piecemap_inner_path = helper.getDirname(file_info["content_inner_path"]) + file_info["piecemap"]
            piecemap_task = None
            if not self.site.storage.isFile(piecemap_inner_path):
                # Start download piecemap
                piecemap_task = super(WorkerManagerPlugin, self).addTask(piecemap_inner_path, priority=30)
                autodownload_bigfile_size_limit = self.site.settings.get("autodownload_bigfile_size_limit", config.autodownload_bigfile_size_limit)
                if "|" not in inner_path and self.site.isDownloadable(inner_path) and file_info["size"] / 1024 / 1024 <= autodownload_bigfile_size_limit:
                    gevent.spawn_later(0.1, self.site.needFile, inner_path + "|all")  # Download all pieces

            if "|" in inner_path:
                # Start download piece
                task = super(WorkerManagerPlugin, self).addTask(inner_path, *args, **kwargs)

                inner_path, file_range = inner_path.split("|")
                pos_from, pos_to = map(int, file_range.split("-"))
                task["piece_i"] = int(pos_from / file_info["piece_size"])
                task["sha512"] = file_info["sha512"]
            else:
                if inner_path in self.site.bad_files:
                    del self.site.bad_files[inner_path]
                if piecemap_task:
                    task = piecemap_task
                else:
                    fake_evt = gevent.event.AsyncResult()  # Don't download anything if no range specified
                    fake_evt.set(True)
                    task = {"evt": fake_evt}

            if not self.site.storage.isFile(inner_path):
                self.site.storage.createSparseFile(inner_path, file_info["size"], file_info["sha512"])
                piece_num = int(math.ceil(float(file_info["size"]) / file_info["piece_size"]))
                self.site.storage.piecefields[file_info["sha512"]].frombytes(b"\x00" * piece_num)
        else:
            task = super(WorkerManagerPlugin, self).addTask(inner_path, *args, **kwargs)
        return task

    def taskAddPeer(self, task, peer):
        if "piece_i" in task:
            if not peer.piecefields[task["sha512"]][task["piece_i"]]:
                if task["sha512"] not in peer.piecefields:
                    gevent.spawn(peer.updatePiecefields, force=True)
                elif not task["peers"]:
                    gevent.spawn(peer.updatePiecefields)

                return False  # Deny to add peers to task if file not in piecefield
        return super(WorkerManagerPlugin, self).taskAddPeer(task, peer)


@PluginManager.registerTo("FileRequest")
class FileRequestPlugin(object):
    def isReadable(self, site, inner_path, file, pos):
        # Peek into file
        if file.read(10) == b"\0" * 10:
            # Looks empty, but makes sures we don't have that piece
            file_info = site.content_manager.getFileInfo(inner_path)
            if "piece_size" in file_info:
                piece_i = int(pos / file_info["piece_size"])
                if not site.storage.piecefields[file_info["sha512"]][piece_i]:
                    return False
        # Seek back to position we want to read
        file.seek(pos)
        return super(FileRequestPlugin, self).isReadable(site, inner_path, file, pos)

    def actionGetPiecefields(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            return False

        # Add peer to site if not added before
        peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True)
        if not peer.connection:  # Just added
            peer.connect(self.connection)  # Assign current connection to peer

        piecefields_packed = {sha512: piecefield.pack() for sha512, piecefield in site.storage.piecefields.items()}
        self.response({"piecefields_packed": piecefields_packed})

    def actionSetPiecefields(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False

        # Add or get peer
        peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True, connection=self.connection)
        if not peer.connection:
            peer.connect(self.connection)

        peer.piecefields = collections.defaultdict(BigfilePiecefieldPacked)
        for sha512, piecefield_packed in params["piecefields_packed"].items():
            peer.piecefields[sha512].unpack(piecefield_packed)
        site.settings["has_bigfile"] = True

        self.response({"ok": "Updated"})


@PluginManager.registerTo("Peer")
class PeerPlugin(object):
    def __getattr__(self, key):
        if key == "piecefields":
            self.piecefields = collections.defaultdict(BigfilePiecefieldPacked)
            return self.piecefields
        elif key == "time_piecefields_updated":
            self.time_piecefields_updated = None
            return self.time_piecefields_updated
        else:
            return super(PeerPlugin, self).__getattr__(key)

    @util.Noparallel(ignore_args=True)
    def updatePiecefields(self, force=False):
        if self.connection and self.connection.handshake.get("rev", 0) < 2190:
            return False  # Not supported

        # Don't update piecefield again in 1 min
        if self.time_piecefields_updated and time.time() - self.time_piecefields_updated < 60 and not force:
            return False

        self.time_piecefields_updated = time.time()
        res = self.request("getPiecefields", {"site": self.site.address})
        if not res or "error" in res:
            return False

        self.piecefields = collections.defaultdict(BigfilePiecefieldPacked)
        try:
            for sha512, piecefield_packed in res["piecefields_packed"].items():
                self.piecefields[sha512].unpack(piecefield_packed)
        except Exception as err:
            self.log("Invalid updatePiecefields response: %s" % Debug.formatException(err))

        return self.piecefields

    def sendMyHashfield(self, *args, **kwargs):
        return super(PeerPlugin, self).sendMyHashfield(*args, **kwargs)

    def updateHashfield(self, *args, **kwargs):
        if self.site.settings.get("has_bigfile"):
            thread = gevent.spawn(self.updatePiecefields, *args, **kwargs)
            back = super(PeerPlugin, self).updateHashfield(*args, **kwargs)
            thread.join()
            return back
        else:
            return super(PeerPlugin, self).updateHashfield(*args, **kwargs)

    def getFile(self, site, inner_path, *args, **kwargs):
        if "|" in inner_path:
            inner_path, file_range = inner_path.split("|")
            pos_from, pos_to = map(int, file_range.split("-"))
            kwargs["pos_from"] = pos_from
            kwargs["pos_to"] = pos_to
        return super(PeerPlugin, self).getFile(site, inner_path, *args, **kwargs)


@PluginManager.registerTo("Site")
class SitePlugin(object):
    def isFileDownloadAllowed(self, inner_path, file_info):
        if "piecemap" in file_info:
            file_size_mb = file_info["size"] / 1024 / 1024
            if config.bigfile_size_limit and file_size_mb > config.bigfile_size_limit:
                self.log.debug(
                    "Bigfile size %s too large: %sMB > %sMB, skipping..." %
                    (inner_path, file_size_mb, config.bigfile_size_limit)
                )
                return False

            file_info = file_info.copy()
            file_info["size"] = file_info["piece_size"]
        return super(SitePlugin, self).isFileDownloadAllowed(inner_path, file_info)

    def getSettingsCache(self):
        back = super(SitePlugin, self).getSettingsCache()
        if self.storage.piecefields:
            back["piecefields"] = {sha512: base64.b64encode(piecefield.pack()).decode("utf8") for sha512, piecefield in self.storage.piecefields.items()}
        return back

    def needFile(self, inner_path, *args, **kwargs):
        if inner_path.endswith("|all"):
            @util.Pooled(20)
            def pooledNeedBigfile(inner_path, *args, **kwargs):
                if inner_path not in self.bad_files:
                    self.log.debug("Cancelled piece, skipping %s" % inner_path)
                    return False
                return self.needFile(inner_path, *args, **kwargs)

            inner_path = inner_path.replace("|all", "")
            file_info = self.needFileInfo(inner_path)
            file_size = file_info["size"]
            piece_size = file_info["piece_size"]

            piece_num = int(math.ceil(float(file_size) / piece_size))

            file_threads = []

            piecefield = self.storage.piecefields.get(file_info["sha512"])

            for piece_i in range(piece_num):
                piece_from = piece_i * piece_size
                piece_to = min(file_size, piece_from + piece_size)
                if not piecefield or not piecefield[piece_i]:
                    inner_path_piece = "%s|%s-%s" % (inner_path, piece_from, piece_to)
                    self.bad_files[inner_path_piece] = self.bad_files.get(inner_path_piece, 1)
                    res = pooledNeedBigfile(inner_path_piece, blocking=False)
                    if res is not True and res is not False:
                        file_threads.append(res)
            gevent.joinall(file_threads)
        else:
            return super(SitePlugin, self).needFile(inner_path, *args, **kwargs)


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("Bigfile plugin")
        group.add_argument('--autodownload_bigfile_size_limit', help='Also download bigfiles smaller than this limit if help distribute option is checked', default=10, metavar="MB", type=int)
        group.add_argument('--bigfile_size_limit', help='Maximum size of downloaded big files', default=False, metavar="MB", type=int)

        return super(ConfigPlugin, self).createArguments()
