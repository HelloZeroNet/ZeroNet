import json
import time
import re
import os
import copy
import base64
import sys

import gevent

from Debug import Debug
from Crypt import CryptHash
from Config import config
from util import helper
from util import Diff
from util import SafeRe
from Peer import PeerHashfield
from .ContentDbDict import ContentDbDict
from Plugin import PluginManager


class VerifyError(Exception):
    pass


class SignError(Exception):
    pass


@PluginManager.acceptPlugins
class ContentManager(object):

    def __init__(self, site):
        self.site = site
        self.log = self.site.log
        self.contents = ContentDbDict(site)
        self.hashfield = PeerHashfield()
        self.has_optional_files = False

    # Load all content.json files
    def loadContents(self):
        if len(self.contents) == 0:
            self.log.info("ContentDb not initialized, load files from filesystem...")
            self.loadContent(add_bad_files=False, delete_removed_files=False)
        self.site.settings["size"], self.site.settings["size_optional"] = self.getTotalSize()

        # Load hashfield cache
        if "hashfield" in self.site.settings.get("cache", {}):
            self.hashfield.frombytes(base64.b64decode(self.site.settings["cache"]["hashfield"]))
            del self.site.settings["cache"]["hashfield"]
        elif self.contents.get("content.json") and self.site.settings["size_optional"] > 0:
            self.site.storage.updateBadFiles()  # No hashfield cache created yet
        self.has_optional_files = bool(self.hashfield)

        self.contents.db.initSite(self.site)

    def getFileChanges(self, old_files, new_files):
        deleted = {key: val for key, val in old_files.items() if key not in new_files}
        deleted_hashes = {val.get("sha512"): key for key, val in old_files.items() if key not in new_files}
        added = {key: val for key, val in new_files.items() if key not in old_files}
        renamed = {}
        for relative_path, node in added.items():
            hash = node.get("sha512")
            if hash in deleted_hashes:
                relative_path_old = deleted_hashes[hash]
                renamed[relative_path_old] = relative_path
                del(deleted[relative_path_old])
        return list(deleted), renamed

    # Load content.json to self.content
    # Return: Changed files ["index.html", "data/messages.json"], Deleted files ["old.jpg"]
    def loadContent(self, content_inner_path="content.json", add_bad_files=True, delete_removed_files=True, load_includes=True, force=False):
        content_inner_path = content_inner_path.strip("/")  # Remove / from beginning
        old_content = self.contents.get(content_inner_path)
        content_path = self.site.storage.getPath(content_inner_path)
        content_dir = helper.getDirname(self.site.storage.getPath(content_inner_path))
        content_inner_dir = helper.getDirname(content_inner_path)

        if os.path.isfile(content_path):
            try:
                # Check if file is newer than what we have
                if not force and old_content and not self.site.settings.get("own"):
                    for line in open(content_path):
                        if '"modified"' not in line:
                            continue
                        match = re.search(r"([0-9\.]+),$", line.strip(" \r\n"))
                        if match and float(match.group(1)) <= old_content.get("modified", 0):
                            self.log.debug("%s loadContent same json file, skipping" % content_inner_path)
                            return [], []

                new_content = self.site.storage.loadJson(content_inner_path)
            except Exception as err:
                self.log.warning("%s load error: %s" % (content_path, Debug.formatException(err)))
                return [], []
        else:
            self.log.debug("Content.json not exist: %s" % content_path)
            return [], []  # Content.json not exist

        try:
            # Get the files where the sha512 changed
            changed = []
            deleted = []
            # Check changed
            for relative_path, info in new_content.get("files", {}).items():
                if "sha512" in info:
                    hash_type = "sha512"
                else:  # Backward compatibility
                    hash_type = "sha1"

                new_hash = info[hash_type]
                if old_content and old_content["files"].get(relative_path):  # We have the file in the old content
                    old_hash = old_content["files"][relative_path].get(hash_type)
                else:  # The file is not in the old content
                    old_hash = None
                if old_hash != new_hash:
                    changed.append(content_inner_dir + relative_path)

            # Check changed optional files
            for relative_path, info in new_content.get("files_optional", {}).items():
                file_inner_path = content_inner_dir + relative_path
                new_hash = info["sha512"]
                if old_content and old_content.get("files_optional", {}).get(relative_path):
                    # We have the file in the old content
                    old_hash = old_content["files_optional"][relative_path].get("sha512")
                    if old_hash != new_hash and self.site.isDownloadable(file_inner_path):
                        changed.append(file_inner_path)  # Download new file
                    elif old_hash != new_hash and self.hashfield.hasHash(old_hash) and not self.site.settings.get("own"):
                        try:
                            old_hash_id = self.hashfield.getHashId(old_hash)
                            self.optionalRemoved(file_inner_path, old_hash_id, old_content["files_optional"][relative_path]["size"])
                            self.optionalDelete(file_inner_path)
                            self.log.debug("Deleted changed optional file: %s" % file_inner_path)
                        except Exception as err:
                            self.log.warning("Error deleting file %s: %s" % (file_inner_path, Debug.formatException(err)))
                else:  # The file is not in the old content
                    if self.site.isDownloadable(file_inner_path):
                        changed.append(file_inner_path)  # Download new file

            # Check deleted
            if old_content:
                old_files = dict(
                    old_content.get("files", {}),
                    **old_content.get("files_optional", {})
                )

                new_files = dict(
                    new_content.get("files", {}),
                    **new_content.get("files_optional", {})
                )

                deleted, renamed = self.getFileChanges(old_files, new_files)

                for relative_path_old, relative_path_new in renamed.items():
                    self.log.debug("Renaming: %s -> %s" % (relative_path_old, relative_path_new))
                    if relative_path_new in new_content.get("files_optional", {}):
                        self.optionalRenamed(content_inner_dir + relative_path_old, content_inner_dir + relative_path_new)
                    if self.site.storage.isFile(relative_path_old):
                        try:
                            self.site.storage.rename(relative_path_old, relative_path_new)
                            if relative_path_new in changed:
                                changed.remove(relative_path_new)
                            self.log.debug("Renamed: %s -> %s" % (relative_path_old, relative_path_new))
                        except Exception as err:
                            self.log.warning("Error renaming file: %s -> %s %s" % (relative_path_old, relative_path_new, err))

                if deleted and not self.site.settings.get("own"):
                    # Deleting files that no longer in content.json
                    for file_relative_path in deleted:
                        file_inner_path = content_inner_dir + file_relative_path
                        try:
                            # Check if the deleted file is optional
                            if old_content.get("files_optional") and old_content["files_optional"].get(file_relative_path):
                                self.optionalDelete(file_inner_path)
                                old_hash = old_content["files_optional"][file_relative_path].get("sha512")
                                if self.hashfield.hasHash(old_hash):
                                    old_hash_id = self.hashfield.getHashId(old_hash)
                                    self.optionalRemoved(file_inner_path, old_hash_id, old_content["files_optional"][file_relative_path]["size"])
                            else:
                                self.site.storage.delete(file_inner_path)

                            self.log.debug("Deleted file: %s" % file_inner_path)
                        except Exception as err:
                            self.log.debug("Error deleting file %s: %s" % (file_inner_path, Debug.formatException(err)))

                    # Cleanup empty dirs
                    tree = {root: [dirs, files] for root, dirs, files in os.walk(self.site.storage.getPath(content_inner_dir))}
                    for root in sorted(tree, key=len, reverse=True):
                        dirs, files = tree[root]
                        if dirs == [] and files == []:
                            root_inner_path = self.site.storage.getInnerPath(root.replace("\\", "/"))
                            self.log.debug("Empty directory: %s, cleaning up." % root_inner_path)
                            try:
                                self.site.storage.deleteDir(root_inner_path)
                                # Remove from tree dict to reflect changed state
                                tree[os.path.dirname(root)][0].remove(os.path.basename(root))
                            except Exception as err:
                                self.log.debug("Error deleting empty directory %s: %s" % (root_inner_path, err))

            # Check archived
            if old_content and "user_contents" in new_content and "archived" in new_content["user_contents"]:
                old_archived = old_content.get("user_contents", {}).get("archived", {})
                new_archived = new_content.get("user_contents", {}).get("archived", {})
                self.log.debug("old archived: %s, new archived: %s" % (len(old_archived), len(new_archived)))
                archived_changed = {
                    key: date_archived
                    for key, date_archived in new_archived.items()
                    if old_archived.get(key) != new_archived[key]
                }
                if archived_changed:
                    self.log.debug("Archived changed: %s" % archived_changed)
                    for archived_dirname, date_archived in archived_changed.items():
                        archived_inner_path = content_inner_dir + archived_dirname + "/content.json"
                        if self.contents.get(archived_inner_path, {}).get("modified", 0) < date_archived:
                            self.removeContent(archived_inner_path)
                            deleted += archived_inner_path
                    self.site.settings["size"], self.site.settings["size_optional"] = self.getTotalSize()

            # Check archived before
            if old_content and "user_contents" in new_content and "archived_before" in new_content["user_contents"]:
                old_archived_before = old_content.get("user_contents", {}).get("archived_before", 0)
                new_archived_before = new_content.get("user_contents", {}).get("archived_before", 0)
                if old_archived_before != new_archived_before:
                    self.log.debug("Archived before changed: %s -> %s" % (old_archived_before, new_archived_before))

                    # Remove downloaded archived files
                    num_removed_contents = 0
                    for archived_inner_path in self.listModified(before=new_archived_before):
                        if archived_inner_path.startswith(content_inner_dir) and archived_inner_path != content_inner_path:
                            self.removeContent(archived_inner_path)
                            num_removed_contents += 1
                    self.site.settings["size"], self.site.settings["size_optional"] = self.getTotalSize()

                    # Remove archived files from download queue
                    num_removed_bad_files = 0
                    for bad_file in list(self.site.bad_files.keys()):
                        if bad_file.endswith("content.json"):
                            del self.site.bad_files[bad_file]
                            num_removed_bad_files += 1

                    if num_removed_bad_files > 0:
                        self.site.worker_manager.removeSolvedFileTasks(mark_as_good=False)
                        self.site.spawn(self.site.update, since=0)

                    self.log.debug("Archived removed contents: %s, removed bad files: %s" % (num_removed_contents, num_removed_bad_files))

            # Load includes
            if load_includes and "includes" in new_content:
                for relative_path, info in list(new_content["includes"].items()):
                    include_inner_path = content_inner_dir + relative_path
                    if self.site.storage.isFile(include_inner_path):  # Content.json exists, load it
                        include_changed, include_deleted = self.loadContent(
                            include_inner_path, add_bad_files=add_bad_files, delete_removed_files=delete_removed_files
                        )
                        if include_changed:
                            changed += include_changed  # Add changed files
                        if include_deleted:
                            deleted += include_deleted  # Add changed files
                    else:  # Content.json not exist, add to changed files
                        self.log.debug("Missing include: %s" % include_inner_path)
                        changed += [include_inner_path]

            # Load blind user includes (all subdir)
            if load_includes and "user_contents" in new_content:
                for relative_dir in os.listdir(content_dir):
                    include_inner_path = content_inner_dir + relative_dir + "/content.json"
                    if not self.site.storage.isFile(include_inner_path):
                        continue  # Content.json not exist
                    include_changed, include_deleted = self.loadContent(
                        include_inner_path, add_bad_files=add_bad_files, delete_removed_files=delete_removed_files,
                        load_includes=False
                    )
                    if include_changed:
                        changed += include_changed  # Add changed files
                    if include_deleted:
                        deleted += include_deleted  # Add changed files

            # Save some memory
            new_content["signs"] = None
            if "cert_sign" in new_content:
                new_content["cert_sign"] = None

            if new_content.get("files_optional"):
                self.has_optional_files = True
            # Update the content
            self.contents[content_inner_path] = new_content
        except Exception as err:
            self.log.warning("%s parse error: %s" % (content_inner_path, Debug.formatException(err)))
            return [], []  # Content.json parse error

        # Add changed files to bad files
        if add_bad_files:
            for inner_path in changed:
                self.site.bad_files[inner_path] = self.site.bad_files.get(inner_path, 0) + 1
            for inner_path in deleted:
                if inner_path in self.site.bad_files:
                    del self.site.bad_files[inner_path]
                self.site.worker_manager.removeSolvedFileTasks()

        if new_content.get("modified", 0) > self.site.settings.get("modified", 0):
            # Dont store modifications in the far future (more than 10 minute)
            self.site.settings["modified"] = min(time.time() + 60 * 10, new_content["modified"])

        return changed, deleted

    def removeContent(self, inner_path):
        inner_dir = helper.getDirname(inner_path)
        try:
            content = self.contents[inner_path]
            files = dict(
                content.get("files", {}),
                **content.get("files_optional", {})
            )
        except Exception as err:
            self.log.debug("Error loading %s for removeContent: %s" % (inner_path, Debug.formatException(err)))
            files = {}
        files["content.json"] = True
        # Deleting files that no longer in content.json
        for file_relative_path in files:
            file_inner_path = inner_dir + file_relative_path
            try:
                self.site.storage.delete(file_inner_path)
                self.log.debug("Deleted file: %s" % file_inner_path)
            except Exception as err:
                self.log.debug("Error deleting file %s: %s" % (file_inner_path, err))
        try:
            self.site.storage.deleteDir(inner_dir)
        except Exception as err:
            self.log.debug("Error deleting dir %s: %s" % (inner_dir, err))

        try:
            del self.contents[inner_path]
        except Exception as err:
            self.log.debug("Error key from contents: %s" % inner_path)

    # Get total size of site
    # Return: 32819 (size of files in kb)
    def getTotalSize(self, ignore=None):
        return self.contents.db.getTotalSize(self.site, ignore)

    def listModified(self, after=None, before=None):
        return self.contents.db.listModified(self.site, after=after, before=before)

    def listContents(self, inner_path="content.json", user_files=False):
        if inner_path not in self.contents:
            return []
        back = [inner_path]
        content_inner_dir = helper.getDirname(inner_path)
        for relative_path in list(self.contents[inner_path].get("includes", {}).keys()):
            include_inner_path = content_inner_dir + relative_path
            back += self.listContents(include_inner_path)
        return back

    # Returns if file with the given modification date is archived or not
    def isArchived(self, inner_path, modified):
        match = re.match(r"(.*)/(.*?)/", inner_path)
        if not match:
            return False
        user_contents_inner_path = match.group(1) + "/content.json"
        relative_directory = match.group(2)

        file_info = self.getFileInfo(user_contents_inner_path)
        if file_info:
            time_archived_before = file_info.get("archived_before", 0)
            time_directory_archived = file_info.get("archived", {}).get(relative_directory, 0)
            if modified <= time_archived_before or modified <= time_directory_archived:
                return True
            else:
                return False
        else:
            return False

    def isDownloaded(self, inner_path, hash_id=None):
        if not hash_id:
            file_info = self.getFileInfo(inner_path)
            if not file_info or "sha512" not in file_info:
                return False
            hash_id = self.hashfield.getHashId(file_info["sha512"])
        return hash_id in self.hashfield

    # Is modified since signing
    def isModified(self, inner_path):
        s = time.time()
        if inner_path.endswith("content.json"):
            try:
                is_valid = self.verifyFile(inner_path, self.site.storage.open(inner_path), ignore_same=False)
                if is_valid:
                    is_modified = False
                else:
                    is_modified = True
            except VerifyError:
                is_modified = True
        else:
            try:
                self.verifyFile(inner_path, self.site.storage.open(inner_path), ignore_same=False)
                is_modified = False
            except VerifyError:
                is_modified = True
        return is_modified

    # Find the file info line from self.contents
    # Return: { "sha512": "c29d73d...21f518", "size": 41 , "content_inner_path": "content.json"}
    def getFileInfo(self, inner_path, new_file=False):
        dirs = inner_path.split("/")  # Parent dirs of content.json
        inner_path_parts = [dirs.pop()]  # Filename relative to content.json
        while True:
            content_inner_path = "%s/content.json" % "/".join(dirs)
            content_inner_path = content_inner_path.strip("/")
            content = self.contents.get(content_inner_path)

            # Check in files
            if content and "files" in content:
                back = content["files"].get("/".join(inner_path_parts))
                if back:
                    back["content_inner_path"] = content_inner_path
                    back["optional"] = False
                    back["relative_path"] = "/".join(inner_path_parts)
                    return back

            # Check in optional files
            if content and "files_optional" in content:  # Check if file in this content.json
                back = content["files_optional"].get("/".join(inner_path_parts))
                if back:
                    back["content_inner_path"] = content_inner_path
                    back["optional"] = True
                    back["relative_path"] = "/".join(inner_path_parts)
                    return back

            # Return the rules if user dir
            if content and "user_contents" in content:
                back = content["user_contents"]
                content_inner_path_dir = helper.getDirname(content_inner_path)
                relative_content_path = inner_path[len(content_inner_path_dir):]
                user_auth_address_match = re.match(r"([A-Za-z0-9]+)/.*", relative_content_path)
                if user_auth_address_match:
                    user_auth_address = user_auth_address_match.group(1)
                    back["content_inner_path"] = "%s%s/content.json" % (content_inner_path_dir, user_auth_address)
                else:
                    back["content_inner_path"] = content_inner_path_dir + "content.json"
                back["optional"] = None
                back["relative_path"] = "/".join(inner_path_parts)
                return back

            if new_file and content:
                back = {}
                back["content_inner_path"] = content_inner_path
                back["relative_path"] = "/".join(inner_path_parts)
                back["optional"] = None
                return back

            # No inner path in this dir, lets try the parent dir
            if dirs:
                inner_path_parts.insert(0, dirs.pop())
            else:  # No more parent dirs
                break

        # Not found
        return False

    # Get rules for the file
    # Return: The rules for the file or False if not allowed
    def getRules(self, inner_path, content=None):
        if not inner_path.endswith("content.json"):  # Find the files content.json first
            file_info = self.getFileInfo(inner_path)
            if not file_info:
                return False  # File not found
            inner_path = file_info["content_inner_path"]

        if inner_path == "content.json":  # Root content.json
            rules = {}
            rules["signers"] = self.getValidSigners(inner_path, content)
            return rules

        dirs = inner_path.split("/")  # Parent dirs of content.json
        inner_path_parts = [dirs.pop()]  # Filename relative to content.json
        inner_path_parts.insert(0, dirs.pop())  # Dont check in self dir
        while True:
            content_inner_path = "%s/content.json" % "/".join(dirs)
            parent_content = self.contents.get(content_inner_path.strip("/"))
            if parent_content and "includes" in parent_content:
                return parent_content["includes"].get("/".join(inner_path_parts))
            elif parent_content and "user_contents" in parent_content:
                return self.getUserContentRules(parent_content, inner_path, content)
            else:  # No inner path in this dir, lets try the parent dir
                if dirs:
                    inner_path_parts.insert(0, dirs.pop())
                else:  # No more parent dirs
                    break

        return False

    # Get rules for a user file
    # Return: The rules of the file or False if not allowed
    def getUserContentRules(self, parent_content, inner_path, content):
        user_contents = parent_content["user_contents"]

        # Delivered for directory
        if "inner_path" in parent_content:
            parent_content_dir = helper.getDirname(parent_content["inner_path"])
            user_address = re.match(r"([A-Za-z0-9]*?)/", inner_path[len(parent_content_dir):]).group(1)
        else:
            user_address = re.match(r".*/([A-Za-z0-9]*?)/.*?$", inner_path).group(1)

        try:
            if not content:
                content = self.site.storage.loadJson(inner_path)  # Read the file if no content specified
            user_urn = "%s/%s" % (content["cert_auth_type"], content["cert_user_id"])  # web/nofish@zeroid.bit
            cert_user_id = content["cert_user_id"]
        except Exception:  # Content.json not exist
            user_urn = "n-a/n-a"
            cert_user_id = "n-a"

        if user_address in user_contents["permissions"]:
            rules = copy.copy(user_contents["permissions"].get(user_address, {}))  # Default rules based on address
        else:
            rules = copy.copy(user_contents["permissions"].get(cert_user_id, {}))  # Default rules based on username

        if rules is False:
            banned = True
            rules = {}
        else:
            banned = False
        if "signers" in rules:
            rules["signers"] = rules["signers"][:]  # Make copy of the signers
        for permission_pattern, permission_rules in list(user_contents["permission_rules"].items()):  # Regexp rules
            if not SafeRe.match(permission_pattern, user_urn):
                continue  # Rule is not valid for user
            # Update rules if its better than current recorded ones
            for key, val in permission_rules.items():
                if key not in rules:
                    if type(val) is list:
                        rules[key] = val[:]  # Make copy
                    else:
                        rules[key] = val
                elif type(val) is int:  # Int, update if larger
                    if val > rules[key]:
                        rules[key] = val
                elif hasattr(val, "startswith"):  # String, update if longer
                    if len(val) > len(rules[key]):
                        rules[key] = val
                elif type(val) is list:  # List, append
                    rules[key] += val

        # Accepted cert signers
        rules["cert_signers"] = user_contents.get("cert_signers", {})
        rules["cert_signers_pattern"] = user_contents.get("cert_signers_pattern")

        if "signers" not in rules:
            rules["signers"] = []

        if not banned:
            rules["signers"].append(user_address)  # Add user as valid signer
        rules["user_address"] = user_address
        rules["includes_allowed"] = False

        return rules

    # Get diffs for changed files
    def getDiffs(self, inner_path, limit=30 * 1024, update_files=True):
        if inner_path not in self.contents:
            return {}
        diffs = {}
        content_inner_path_dir = helper.getDirname(inner_path)
        for file_relative_path in self.contents[inner_path].get("files", {}):
            file_inner_path = content_inner_path_dir + file_relative_path
            if self.site.storage.isFile(file_inner_path + "-new"):  # New version present
                diffs[file_relative_path] = Diff.diff(
                    list(self.site.storage.open(file_inner_path)),
                    list(self.site.storage.open(file_inner_path + "-new")),
                    limit=limit
                )
                if update_files:
                    self.site.storage.delete(file_inner_path)
                    self.site.storage.rename(file_inner_path + "-new", file_inner_path)
            if self.site.storage.isFile(file_inner_path + "-old"):  # Old version present
                diffs[file_relative_path] = Diff.diff(
                    list(self.site.storage.open(file_inner_path + "-old")),
                    list(self.site.storage.open(file_inner_path)),
                    limit=limit
                )
                if update_files:
                    self.site.storage.delete(file_inner_path + "-old")
        return diffs

    def hashFile(self, dir_inner_path, file_relative_path, optional=False):
        back = {}
        file_inner_path = dir_inner_path + "/" + file_relative_path

        file_path = self.site.storage.getPath(file_inner_path)
        file_size = os.path.getsize(file_path)
        sha512sum = CryptHash.sha512sum(file_path)  # Calculate sha512 sum of file
        if optional and not self.hashfield.hasHash(sha512sum):
            self.optionalDownloaded(file_inner_path, self.hashfield.getHashId(sha512sum), file_size, own=True)

        back[file_relative_path] = {"sha512": sha512sum, "size": os.path.getsize(file_path)}
        return back

    def isValidRelativePath(self, relative_path):
        if ".." in relative_path.replace("\\", "/").split("/"):
            return False
        elif len(relative_path) > 255:
            return False
        elif relative_path[0] in ("/", "\\"):  # Starts with
            return False
        elif relative_path[-1] in (".", " "):  # Ends with
            return False
        elif re.match(r".*(^|/)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]|CONOUT\$|CONIN\$)(\.|/|$)", relative_path, re.IGNORECASE):  # Protected on Windows
            return False
        else:
            return re.match(r"^[^\x00-\x1F\"*:<>?\\|]+$", relative_path)

    def sanitizePath(self, inner_path):
        return re.sub("[\x00-\x1F\"*:<>?\\|]", "", inner_path)

    # Hash files in directory
    def hashFiles(self, dir_inner_path, ignore_pattern=None, optional_pattern=None):
        files_node = {}
        files_optional_node = {}
        db_inner_path = self.site.storage.getDbFile()
        if dir_inner_path and not self.isValidRelativePath(dir_inner_path):
            ignored = True
            self.log.error("- [ERROR] Only ascii encoded directories allowed: %s" % dir_inner_path)

        for file_relative_path in self.site.storage.walk(dir_inner_path, ignore_pattern):
            file_name = helper.getFilename(file_relative_path)

            ignored = optional = False
            if file_name == "content.json":
                ignored = True
            elif file_name.startswith(".") or file_name.endswith("-old") or file_name.endswith("-new"):
                ignored = True
            elif not self.isValidRelativePath(file_relative_path):
                ignored = True
                self.log.error("- [ERROR] Invalid filename: %s" % file_relative_path)
            elif dir_inner_path == "" and db_inner_path and file_relative_path.startswith(db_inner_path):
                ignored = True
            elif optional_pattern and SafeRe.match(optional_pattern, file_relative_path):
                optional = True

            if ignored:  # Ignore content.json, defined regexp and files starting with .
                self.log.info("- [SKIPPED] %s" % file_relative_path)
            else:
                if optional:
                    self.log.info("- [OPTIONAL] %s" % file_relative_path)
                    files_optional_node.update(
                        self.hashFile(dir_inner_path, file_relative_path, optional=True)
                    )
                else:
                    self.log.info("- %s" % file_relative_path)
                    files_node.update(
                        self.hashFile(dir_inner_path, file_relative_path)
                    )
        return files_node, files_optional_node

    def serializeForSigning(self, content):
        if "sign" in content:
            del(content["sign"])  # The file signed without the sign
        if "signs" in content:
            del(content["signs"])  # The file signed without the signs

        sign_content = json.dumps(content, sort_keys=True)  # Dump the json to string to remove whitespaces

        # Fix float representation error on Android
        modified = content["modified"]
        if config.fix_float_decimals and type(modified) is float and not str(modified).endswith(".0"):
            modified_fixed = "{:.6f}".format(modified).strip("0.")
            sign_content = sign_content.replace(
                '"modified": %s' % repr(modified),
                '"modified": %s' % modified_fixed
            )

        return sign_content

    # Create and sign a content.json
    # Return: The new content if filewrite = False
    def sign(self, inner_path="content.json", privatekey=None, filewrite=True, update_changed_files=False, extend=None, remove_missing_optional=False):
        if not inner_path.endswith("content.json"):
            raise SignError("Invalid file name, you can only sign content.json files")

        if inner_path in self.contents:
            content = self.contents.get(inner_path)
            if content and content.get("cert_sign", False) is None and self.site.storage.isFile(inner_path):
                # Recover cert_sign from file
                content["cert_sign"] = self.site.storage.loadJson(inner_path).get("cert_sign")
        else:
            content = None
        if not content:  # Content not exist yet, load default one
            self.log.info("File %s not exist yet, loading default values..." % inner_path)

            if self.site.storage.isFile(inner_path):
                content = self.site.storage.loadJson(inner_path)
                if "files" not in content:
                    content["files"] = {}
                if "signs" not in content:
                    content["signs"] = {}
            else:
                content = {"files": {}, "signs": {}}  # Default content.json

            if inner_path == "content.json":  # It's the root content.json, add some more fields
                content["title"] = "%s - ZeroNet_" % self.site.address
                content["description"] = ""
                content["signs_required"] = 1
                content["ignore"] = ""

        if extend:
            # Add extend keys if not exists
            for key, val in list(extend.items()):
                if not content.get(key):
                    content[key] = val
                    self.log.info("Extending content.json with: %s" % key)

        directory = helper.getDirname(self.site.storage.getPath(inner_path))
        inner_directory = helper.getDirname(inner_path)
        self.log.info("Opening site data directory: %s..." % directory)

        changed_files = [inner_path]
        files_node, files_optional_node = self.hashFiles(
            helper.getDirname(inner_path), content.get("ignore"), content.get("optional")
        )

        if not remove_missing_optional:
            for file_inner_path, file_details in content.get("files_optional", {}).items():
                if file_inner_path not in files_optional_node:
                    files_optional_node[file_inner_path] = file_details

        # Find changed files
        files_merged = files_node.copy()
        files_merged.update(files_optional_node)
        for file_relative_path, file_details in files_merged.items():
            old_hash = content.get("files", {}).get(file_relative_path, {}).get("sha512")
            new_hash = files_merged[file_relative_path]["sha512"]
            if old_hash != new_hash:
                changed_files.append(inner_directory + file_relative_path)

        self.log.debug("Changed files: %s" % changed_files)
        if update_changed_files:
            for file_path in changed_files:
                self.site.storage.onUpdated(file_path)

        # Generate new content.json
        self.log.info("Adding timestamp and sha512sums to new content.json...")

        new_content = content.copy()  # Create a copy of current content.json
        new_content["files"] = files_node  # Add files sha512 hash
        if files_optional_node:
            new_content["files_optional"] = files_optional_node
        elif "files_optional" in new_content:
            del new_content["files_optional"]

        new_content["modified"] = int(time.time())  # Add timestamp
        if inner_path == "content.json":
            new_content["zeronet_version"] = config.version
            new_content["signs_required"] = content.get("signs_required", 1)

        new_content["address"] = self.site.address
        new_content["inner_path"] = inner_path

        # Verify private key
        from Crypt import CryptBitcoin
        self.log.info("Verifying private key...")
        privatekey_address = CryptBitcoin.privatekeyToAddress(privatekey)
        valid_signers = self.getValidSigners(inner_path, new_content)
        if privatekey_address not in valid_signers:
            raise SignError(
                "Private key invalid! Valid signers: %s, Private key address: %s" %
                (valid_signers, privatekey_address)
            )
        self.log.info("Correct %s in valid signers: %s" % (privatekey_address, valid_signers))

        if inner_path == "content.json" and privatekey_address == self.site.address:
            # If signing using the root key, then sign the valid signers
            signers_data = "%s:%s" % (new_content["signs_required"], ",".join(valid_signers))
            new_content["signers_sign"] = CryptBitcoin.sign(str(signers_data), privatekey)
            if not new_content["signers_sign"]:
                self.log.info("Old style address, signers_sign is none")

        self.log.info("Signing %s..." % inner_path)

        sign_content = self.serializeForSigning(new_content)
        sign = CryptBitcoin.sign(sign_content, privatekey)
        # new_content["signs"] = content.get("signs", {}) # TODO: Multisig
        if sign:  # If signing is successful (not an old address)
            new_content["signs"] = {}
            new_content["signs"][privatekey_address] = sign

        self.verifyContent(inner_path, new_content)

        if filewrite:
            self.log.info("Saving to %s..." % inner_path)
            self.site.storage.writeJson(inner_path, new_content)
            self.contents[inner_path] = new_content

        self.log.info("File %s signed!" % inner_path)

        if filewrite:  # Written to file
            return True
        else:  # Return the new content
            return new_content

    # The valid signers of content.json file
    # Return: ["1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6", "13ReyhCsjhpuCVahn1DHdf6eMqqEVev162"]
    def getValidSigners(self, inner_path, content=None):
        valid_signers = []
        if inner_path == "content.json":  # Root content.json
            if "content.json" in self.contents and "signers" in self.contents["content.json"]:
                valid_signers += self.contents["content.json"]["signers"][:]
        else:
            rules = self.getRules(inner_path, content)
            if rules and "signers" in rules:
                valid_signers += rules["signers"]

        if self.site.address not in valid_signers:
            valid_signers.append(self.site.address)  # Site address always valid
        return valid_signers

    # Return: The required number of valid signs for the content.json
    def getSignsRequired(self, inner_path, content=None):
        return 1  # Todo: Multisig

    def verifyCertSign(self, user_address, user_auth_type, user_name, issuer_address, sign):
        from Crypt import CryptBitcoin
        cert_subject = "%s#%s/%s" % (user_address, user_auth_type, user_name)
        return CryptBitcoin.verify(cert_subject, issuer_address, sign)

    def verifyCert(self, inner_path, content):
        rules = self.getRules(inner_path, content)

        if not rules:
            raise VerifyError("No rules for this file")

        if not rules.get("cert_signers") and not rules.get("cert_signers_pattern"):
            return True  # Does not need cert

        if "cert_user_id" not in content:
            raise VerifyError("Missing cert_user_id")

        if content["cert_user_id"].count("@") != 1:
            raise VerifyError("Invalid domain in cert_user_id")

        name, domain = content["cert_user_id"].rsplit("@", 1)
        cert_address = rules["cert_signers"].get(domain)
        if not cert_address:  # Unknown Cert signer
            if rules.get("cert_signers_pattern") and SafeRe.match(rules["cert_signers_pattern"], domain):
                cert_address = domain
            else:
                raise VerifyError("Invalid cert signer: %s" % domain)

        return self.verifyCertSign(rules["user_address"], content["cert_auth_type"], name, cert_address, content["cert_sign"])

    # Checks if the content.json content is valid
    # Return: True or False
    def verifyContent(self, inner_path, content):
        content_size = len(json.dumps(content, indent=1)) + sum([file["size"] for file in list(content["files"].values()) if file["size"] >= 0])  # Size of new content
        # Calculate old content size
        old_content = self.contents.get(inner_path)
        if old_content:
            old_content_size = len(json.dumps(old_content, indent=1)) + sum([file["size"] for file in list(old_content.get("files", {}).values())])
            old_content_size_optional = sum([file["size"] for file in list(old_content.get("files_optional", {}).values())])
        else:
            old_content_size = 0
            old_content_size_optional = 0

        # Reset site site on first content.json
        if not old_content and inner_path == "content.json":
            self.site.settings["size"] = 0

        content_size_optional = sum([file["size"] for file in list(content.get("files_optional", {}).values()) if file["size"] >= 0])
        site_size = self.site.settings["size"] - old_content_size + content_size  # Site size without old content plus the new
        site_size_optional = self.site.settings["size_optional"] - old_content_size_optional + content_size_optional  # Site size without old content plus the new

        site_size_limit = self.site.getSizeLimit() * 1024 * 1024

        # Check site address
        if content.get("address") and content["address"] != self.site.address:
            raise VerifyError("Wrong site address: %s != %s" % (content["address"], self.site.address))

        # Check file inner path
        if content.get("inner_path") and content["inner_path"] != inner_path:
            raise VerifyError("Wrong inner_path: %s" % content["inner_path"])

        # If our content.json file bigger than the size limit throw error
        if inner_path == "content.json":
            content_size_file = len(json.dumps(content, indent=1))
            if content_size_file > site_size_limit:
                # Save site size to display warning
                self.site.settings["size"] = site_size
                task = self.site.worker_manager.tasks.findTask(inner_path)
                if task:  # Dont try to download from other peers
                    self.site.worker_manager.failTask(task)
                raise VerifyError("Content too large %s B > %s B, aborting task..." % (site_size, site_size_limit))

        # Verify valid filenames
        for file_relative_path in list(content.get("files", {}).keys()) + list(content.get("files_optional", {}).keys()):
            if not self.isValidRelativePath(file_relative_path):
                raise VerifyError("Invalid relative path: %s" % file_relative_path)

        if inner_path == "content.json":
            self.site.settings["size"] = site_size
            self.site.settings["size_optional"] = site_size_optional
            return True  # Root content.json is passed
        else:
            if self.verifyContentInclude(inner_path, content, content_size, content_size_optional):
                self.site.settings["size"] = site_size
                self.site.settings["size_optional"] = site_size_optional
                return True
            else:
                raise VerifyError("Content verify error")

    def verifyContentInclude(self, inner_path, content, content_size, content_size_optional):
        # Load include details
        rules = self.getRules(inner_path, content)
        if not rules:
            raise VerifyError("No rules")

        # Check include size limit
        if rules.get("max_size") is not None:  # Include size limit
            if content_size > rules["max_size"]:
                raise VerifyError("Include too large %sB > %sB" % (content_size, rules["max_size"]))

        if rules.get("max_size_optional") is not None:  # Include optional files limit
            if content_size_optional > rules["max_size_optional"]:
                raise VerifyError("Include optional files too large %sB > %sB" % (
                    content_size_optional, rules["max_size_optional"])
                )

        # Filename limit
        if rules.get("files_allowed"):
            for file_inner_path in list(content["files"].keys()):
                if not SafeRe.match(r"^%s$" % rules["files_allowed"], file_inner_path):
                    raise VerifyError("File not allowed: %s" % file_inner_path)

        if rules.get("files_allowed_optional"):
            for file_inner_path in list(content.get("files_optional", {}).keys()):
                if not SafeRe.match(r"^%s$" % rules["files_allowed_optional"], file_inner_path):
                    raise VerifyError("Optional file not allowed: %s" % file_inner_path)

        # Check if content includes allowed
        if rules.get("includes_allowed") is False and content.get("includes"):
            raise VerifyError("Includes not allowed")

        return True  # All good

    def verifyContentFile(self, inner_path, file, ignore_same=True):
        from Crypt import CryptBitcoin

        if type(file) is dict:
            new_content = file
        else:
            try:
                if sys.version_info.major == 3 and sys.version_info.minor < 6:
                    new_content = json.loads(file.read().decode("utf8"))
                else:
                    new_content = json.load(file)
            except Exception as err:
                raise VerifyError("Invalid json file: %s" % err)
        if inner_path in self.contents:
            old_content = self.contents.get(inner_path, {"modified": 0})
            # Checks if its newer the ours
            if old_content["modified"] == new_content["modified"] and ignore_same:  # Ignore, have the same content.json
                return None
            elif old_content["modified"] > new_content["modified"]:  # We have newer
                raise VerifyError(
                    "We have newer (Our: %s, Sent: %s)" %
                    (old_content["modified"], new_content["modified"])
                )
        if new_content["modified"] > time.time() + 60 * 60 * 24:  # Content modified in the far future (allow 1 day+)
            raise VerifyError("Modify timestamp is in the far future!")
        if self.isArchived(inner_path, new_content["modified"]):
            if inner_path in self.site.bad_files:
                del self.site.bad_files[inner_path]
            raise VerifyError("This file is archived!")
        # Check sign
        sign = new_content.get("sign")
        signs = new_content.get("signs", {})
        sign_content = self.serializeForSigning(new_content)

        if signs:  # New style signing
            valid_signers = self.getValidSigners(inner_path, new_content)
            signs_required = self.getSignsRequired(inner_path, new_content)

            if inner_path == "content.json" and len(valid_signers) > 1:  # Check signers_sign on root content.json
                signers_data = "%s:%s" % (signs_required, ",".join(valid_signers))
                if not CryptBitcoin.verify(signers_data, self.site.address, new_content["signers_sign"]):
                    raise VerifyError("Invalid signers_sign!")

            if inner_path != "content.json" and not self.verifyCert(inner_path, new_content):  # Check if cert valid
                raise VerifyError("Invalid cert!")

            valid_signs = 0
            for address in valid_signers:
                if address in signs:
                    valid_signs += CryptBitcoin.verify(sign_content, address, signs[address])
                if valid_signs >= signs_required:
                    break  # Break if we has enough signs
            if valid_signs < signs_required:
                raise VerifyError("Valid signs: %s/%s" % (valid_signs, signs_required))
            else:
                return self.verifyContent(inner_path, new_content)
        elif sign:  # Old style signing
            raise VerifyError("Invalid old-style sign")
        else:
            raise VerifyError("Not signed")

    def verifyOrdinaryFile(self, inner_path, file, ignore_same=True):
        file_info = self.getFileInfo(inner_path)
        if file_info:
            if CryptHash.sha512sum(file) != file_info.get("sha512", ""):
                raise VerifyError("Invalid hash")

            if file_info.get("size", 0) != file.tell():
                raise VerifyError(
                    "File size does not match %s <> %s" %
                    (inner_path, file.tell(), file_info.get("size", 0))
                )

            return True

        else:  # File not in content.json
            raise VerifyError("File not in content.json")

    # Verify file validity
    # Return: None = Same as before, False = Invalid, True = Valid
    def verifyFile(self, inner_path, file, ignore_same=True):
        try:
            if inner_path.endswith("content.json"):
                return self.verifyContentFile(inner_path, file, ignore_same)
            else:
                return self.verifyOrdinaryFile(inner_path, file, ignore_same)
        except Exception as err:
            self.log.info("%s: verify error: %s" % (inner_path, Debug.formatException(err)))
            raise err

    def optionalDelete(self, inner_path):
        self.site.storage.delete(inner_path)

    def optionalDownloaded(self, inner_path, hash_id, size=None, own=False):
        if size is None:
            size = self.site.storage.getSize(inner_path)

        done = self.hashfield.appendHashId(hash_id)
        self.site.settings["optional_downloaded"] += size
        return done

    def optionalRemoved(self, inner_path, hash_id, size=None):
        if size is None:
            size = self.site.storage.getSize(inner_path)
        done = self.hashfield.removeHashId(hash_id)

        self.site.settings["optional_downloaded"] -= size
        return done

    def optionalRenamed(self, inner_path_old, inner_path_new):
        return True
