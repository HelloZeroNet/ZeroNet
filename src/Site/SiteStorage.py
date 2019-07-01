import os
import re
import shutil
import json
import time
import sys
from collections import defaultdict

import sqlite3
import gevent.event

import util
from util import SafeRe
from Db.Db import Db, DbTableError
from Debug import Debug
from Config import config
from util import helper
from Plugin import PluginManager
from Translate import translate as _


@PluginManager.acceptPlugins
class SiteStorage(object):
    def __init__(self, site, allow_create=True):
        self.site = site
        self.directory = "%s/%s" % (config.data_dir, self.site.address)  # Site data diretory
        self.allowed_dir = os.path.abspath(self.directory)  # Only serve file within this dir
        self.log = site.log
        self.db = None  # Db class
        self.db_checked = False  # Checked db tables since startup
        self.event_db_busy = None  # Gevent AsyncResult if db is working on rebuild
        self.has_db = self.isFile("dbschema.json")  # The site has schema

        if not os.path.isdir(self.directory):
            if allow_create:
                os.mkdir(self.directory)  # Create directory if not found
            else:
                raise Exception("Directory not exists: %s" % self.directory)

    def getDbFile(self):
        if self.isFile("dbschema.json"):
            schema = self.loadJson("dbschema.json")
            return schema["db_file"]
        else:
            return False

    # Create new databaseobject  with the site's schema
    def openDb(self, close_idle=False):
        schema = self.getDbSchema()
        db_path = self.getPath(schema["db_file"])
        return Db(schema, db_path, close_idle=close_idle)

    def closeDb(self):
        if self.db:
            self.db.close()
        self.event_db_busy = None
        self.db = None

    def getDbSchema(self):
        try:
            schema = self.loadJson("dbschema.json")
        except Exception as err:
            raise Exception("dbschema.json is not a valid JSON: %s" % err)
        return schema

    # Return db class
    def getDb(self):
        if not self.db:
            self.log.debug("No database, waiting for dbschema.json...")
            self.site.needFile("dbschema.json", priority=3)
            self.has_db = self.isFile("dbschema.json")  # Recheck if dbschema exist
            if self.has_db:
                schema = self.getDbSchema()
                db_path = self.getPath(schema["db_file"])
                if not os.path.isfile(db_path) or os.path.getsize(db_path) == 0:
                    try:
                        self.rebuildDb()
                    except Exception as err:
                        self.log.error(err)
                        pass

                if self.db:
                    self.db.close()
                self.db = self.openDb(close_idle=True)
                try:
                    changed_tables = self.db.checkTables()
                    if changed_tables:
                        self.rebuildDb(delete_db=False)  # TODO: only update the changed table datas
                except sqlite3.OperationalError:
                    pass

        return self.db

    def updateDbFile(self, inner_path, file=None, cur=None):
        path = self.getPath(inner_path)
        return self.getDb().updateJson(path, file, cur)

    # Return possible db files for the site
    def getDbFiles(self):
        found = 0
        for content_inner_path, content in self.site.content_manager.contents.items():
            # content.json file itself
            if self.isFile(content_inner_path):
                yield content_inner_path, self.getPath(content_inner_path)
            else:
                self.log.error("[MISSING] %s" % content_inner_path)
            # Data files in content.json
            content_inner_path_dir = helper.getDirname(content_inner_path)  # Content.json dir relative to site
            for file_relative_path in list(content.get("files", {}).keys()) + list(content.get("files_optional", {}).keys()):
                if not file_relative_path.endswith(".json") and not file_relative_path.endswith("json.gz"):
                    continue  # We only interesed in json files
                file_inner_path = content_inner_path_dir + file_relative_path  # File Relative to site dir
                file_inner_path = file_inner_path.strip("/")  # Strip leading /
                if self.isFile(file_inner_path):
                    yield file_inner_path, self.getPath(file_inner_path)
                else:
                    self.log.error("[MISSING] %s" % file_inner_path)
                found += 1
                if found % 100 == 0:
                    time.sleep(0.001)  # Context switch to avoid UI block

    # Rebuild sql cache
    @util.Noparallel()
    def rebuildDb(self, delete_db=True):
        self.log.info("Rebuilding db...")
        self.has_db = self.isFile("dbschema.json")
        if not self.has_db:
            return False

        schema = self.loadJson("dbschema.json")
        db_path = self.getPath(schema["db_file"])
        if os.path.isfile(db_path) and delete_db:
            if self.db:
                self.closeDb()  # Close db if open
                time.sleep(0.5)
            self.log.info("Deleting %s" % db_path)
            try:
                os.unlink(db_path)
            except Exception as err:
                self.log.error("Delete error: %s" % err)

        if not self.db:
            self.db = self.openDb()
        self.event_db_busy = gevent.event.AsyncResult()

        self.log.info("Creating tables...")

        # raise DbTableError if not valid
        self.db.checkTables()

        cur = self.db.getCursor()
        cur.logging = False
        s = time.time()
        self.log.info("Getting db files...")
        db_files = list(self.getDbFiles())
        num_imported = 0
        num_total = len(db_files)
        num_error = 0

        self.log.info("Importing data...")
        try:
            if num_total > 100:
                self.site.messageWebsocket(_["Database rebuilding...<br>Imported {0} of {1} files (error: {2})..."].format("0000", num_total, num_error), "rebuild", 0)
            for file_inner_path, file_path in db_files:
                try:
                    if self.updateDbFile(file_inner_path, file=open(file_path, "rb"), cur=cur):
                        num_imported += 1
                except Exception as err:
                    self.log.error("Error importing %s: %s" % (file_inner_path, Debug.formatException(err)))
                    num_error += 1

                if num_imported and num_imported % 100 == 0:
                    self.site.messageWebsocket(
                        _["Database rebuilding...<br>Imported {0} of {1} files (error: {2})..."].format(num_imported, num_total, num_error),
                        "rebuild",
                        int(float(num_imported) / num_total * 100)
                    )
                    time.sleep(0.001)  # Context switch to avoid UI block

        finally:
            cur.close()
            if num_total > 100:
                self.site.messageWebsocket(_["Database rebuilding...<br>Imported {0} of {1} files (error: {2})..."].format(num_imported, num_total, num_error), "rebuild", 100)
            self.log.info("Imported %s data file in %.3fs" % (num_imported, time.time() - s))
            self.event_db_busy.set(True)  # Event done, notify waiters
            self.event_db_busy = None  # Clear event

        return True

    # Execute sql query or rebuild on dberror
    def query(self, query, params=None):
        if not query.strip().upper().startswith("SELECT"):
            raise Exception("Only SELECT query supported")

        if self.event_db_busy:  # Db not ready for queries
            self.log.debug("Wating for db...")
            self.event_db_busy.get()  # Wait for event
        try:
            res = self.getDb().execute(query, params)
        except sqlite3.DatabaseError as err:
            if err.__class__.__name__ == "DatabaseError":
                self.log.error("Database error: %s, query: %s, try to rebuilding it..." % (err, query))
                try:
                    self.rebuildDb()
                except sqlite3.OperationalError:
                    pass
                res = self.db.cur.execute(query, params)
            else:
                raise err
        return res

    # Open file object
    def open(self, inner_path, mode="rb", create_dirs=False, **kwargs):
        file_path = self.getPath(inner_path)
        if create_dirs:
            file_dir = os.path.dirname(file_path)
            if not os.path.isdir(file_dir):
                os.makedirs(file_dir)
        return open(file_path, mode, **kwargs)

    # Open file object
    def read(self, inner_path, mode="rb"):
        return open(self.getPath(inner_path), mode).read()

    # Write content to file
    def write(self, inner_path, content):
        file_path = self.getPath(inner_path)
        # Create dir if not exist
        file_dir = os.path.dirname(file_path)
        if not os.path.isdir(file_dir):
            os.makedirs(file_dir)
        # Write file
        if hasattr(content, 'read'):  # File-like object
            with open(file_path, "wb") as file:
                shutil.copyfileobj(content, file)  # Write buff to disk
        else:  # Simple string
            if inner_path == "content.json" and os.path.isfile(file_path):
                helper.atomicWrite(file_path, content)
            else:
                with open(file_path, "wb") as file:
                    file.write(content)
        del content
        self.onUpdated(inner_path)

    # Remove file from filesystem
    def delete(self, inner_path):
        file_path = self.getPath(inner_path)
        os.unlink(file_path)
        self.onUpdated(inner_path, file=False)

    def deleteDir(self, inner_path):
        dir_path = self.getPath(inner_path)
        os.rmdir(dir_path)

    def rename(self, inner_path_before, inner_path_after):
        for retry in range(3):
            rename_err = None
            # To workaround "The process cannot access the file beacause it is being used by another process." error
            try:
                os.rename(self.getPath(inner_path_before), self.getPath(inner_path_after))
                break
            except Exception as err:
                rename_err = err
                self.log.error("%s rename error: %s (retry #%s)" % (inner_path_before, err, retry))
                time.sleep(0.1 + retry)
        if rename_err:
            raise rename_err

    # List files from a directory
    def walk(self, dir_inner_path, ignore=None):
        directory = self.getPath(dir_inner_path)
        for root, dirs, files in os.walk(directory):
            root = root.replace("\\", "/")
            root_relative_path = re.sub("^%s" % re.escape(directory), "", root).lstrip("/")
            for file_name in files:
                if root_relative_path:  # Not root dir
                    file_relative_path = root_relative_path + "/" + file_name
                else:
                    file_relative_path = file_name

                if ignore and SafeRe.match(ignore, file_relative_path):
                    continue

                yield file_relative_path

            # Don't scan directory that is in the ignore pattern
            if ignore:
                dirs_filtered = []
                for dir_name in dirs:
                    if root_relative_path:
                        dir_relative_path = root_relative_path + "/" + dir_name
                    else:
                        dir_relative_path = dir_name

                    if ignore == ".*" or re.match(".*([|(]|^)%s([|)]|$)" % re.escape(dir_relative_path + "/.*"), ignore):
                        continue

                    dirs_filtered.append(dir_name)
                dirs[:] = dirs_filtered

    # list directories in a directory
    def list(self, dir_inner_path):
        directory = self.getPath(dir_inner_path)
        return os.listdir(directory)

    # Site content updated
    def onUpdated(self, inner_path, file=None):
        # Update Sql cache
        if inner_path == "dbschema.json":
            self.has_db = self.isFile("dbschema.json")
            # Reopen DB to check changes
            if self.has_db:
                self.closeDb()
                self.getDb()
        elif not config.disable_db and (inner_path.endswith(".json") or inner_path.endswith(".json.gz")) and self.has_db:  # Load json file to db
            if config.verbose:
                self.log.debug("Loading json file to db: %s (file: %s)" % (inner_path, file))
            try:
                self.updateDbFile(inner_path, file)
            except Exception as err:
                self.log.error("Json %s load error: %s" % (inner_path, Debug.formatException(err)))
                self.closeDb()

    # Load and parse json file
    def loadJson(self, inner_path):
        with self.open(inner_path, "r", encoding="utf8") as file:
            return json.load(file)

    def formatJson(self, data):
        content = json.dumps(data, indent=1, sort_keys=True)

        # Make it a little more compact by removing unnecessary white space
        def compact_dict(match):
            if "\n" in match.group(0):
                return match.group(0).replace(match.group(1), match.group(1).strip())
            else:
                return match.group(0)

        content = re.sub("\{(\n[^,\[\{]{10,100}?)\}[, ]{0,2}\n", compact_dict, content, flags=re.DOTALL)

        def compact_list(match):
            if "\n" in match.group(0):
                stripped_lines = re.sub("\n[ ]*", "", match.group(1))
                return match.group(0).replace(match.group(1), stripped_lines)
            else:
                return match.group(0)

        content = re.sub("\[([^\[\{]{2,300}?)\][, ]{0,2}\n", compact_list, content, flags=re.DOTALL)

        # Remove end of line whitespace
        content = re.sub("(?m)[ ]+$", "", content)
        return content

    # Write formatted json file
    def writeJson(self, inner_path, data):
        # Write to disk
        self.write(inner_path, self.formatJson(data).encode("utf8"))

    # Get file size
    def getSize(self, inner_path):
        path = self.getPath(inner_path)
        try:
            return os.path.getsize(path)
        except:
            return 0

    # File exist
    def isFile(self, inner_path):
        return os.path.isfile(self.getPath(inner_path))

    # File or directory exist
    def isExists(self, inner_path):
        return os.path.exists(self.getPath(inner_path))

    # Dir exist
    def isDir(self, inner_path):
        return os.path.isdir(self.getPath(inner_path))

    # Security check and return path of site's file
    def getPath(self, inner_path):
        inner_path = inner_path.replace("\\", "/")  # Windows separator fix
        if not inner_path:
            return self.directory

        if "../" in inner_path:
            raise Exception("File not allowed: %s" % inner_path)

        return "%s/%s" % (self.directory, inner_path)

    # Get site dir relative path
    def getInnerPath(self, path):
        if path == self.directory:
            inner_path = ""
        else:
            if path.startswith(self.directory):
                inner_path = path[len(self.directory) + 1:]
            else:
                raise Exception("File not allowed: %s" % path)
        return inner_path

    # Verify all files sha512sum using content.json
    def verifyFiles(self, quick_check=False, add_optional=False, add_changed=True):
        bad_files = []
        back = defaultdict(int)
        back["bad_files"] = bad_files
        i = 0
        self.log.debug("Verifing files...")

        if not self.site.content_manager.contents.get("content.json"):  # No content.json, download it first
            self.log.debug("VerifyFile content.json not exists")
            self.site.needFile("content.json", update=True)  # Force update to fix corrupt file
            self.site.content_manager.loadContent()  # Reload content.json
        for content_inner_path, content in list(self.site.content_manager.contents.items()):
            back["num_content"] += 1
            i += 1
            if i % 50 == 0:
                time.sleep(0.001)  # Context switch to avoid gevent hangs
            if not os.path.isfile(self.getPath(content_inner_path)):  # Missing content.json file
                back["num_content_missing"] += 1
                self.log.debug("[MISSING] %s" % content_inner_path)
                bad_files.append(content_inner_path)

            for file_relative_path in list(content.get("files", {}).keys()):
                back["num_file"] += 1
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to site dir
                file_inner_path = file_inner_path.strip("/")  # Strip leading /
                file_path = self.getPath(file_inner_path)
                if not os.path.isfile(file_path):
                    back["num_file_missing"] += 1
                    self.log.debug("[MISSING] %s" % file_inner_path)
                    bad_files.append(file_inner_path)
                    continue

                if quick_check:
                    ok = os.path.getsize(file_path) == content["files"][file_relative_path]["size"]
                    if not ok:
                        err = "Invalid size"
                else:
                    try:
                        ok = self.site.content_manager.verifyFile(file_inner_path, open(file_path, "rb"))
                    except Exception as err:
                        ok = False

                if not ok:
                    back["num_file_invalid"] += 1
                    self.log.debug("[INVALID] %s: %s" % (file_inner_path, err))
                    if add_changed or content.get("cert_user_id"):  # If updating own site only add changed user files
                        bad_files.append(file_inner_path)

            # Optional files
            optional_added = 0
            optional_removed = 0
            for file_relative_path in list(content.get("files_optional", {}).keys()):
                back["num_optional"] += 1
                file_node = content["files_optional"][file_relative_path]
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to site dir
                file_inner_path = file_inner_path.strip("/")  # Strip leading /
                file_path = self.getPath(file_inner_path)
                hash_id = self.site.content_manager.hashfield.getHashId(file_node["sha512"])
                if not os.path.isfile(file_path):
                    if self.site.content_manager.isDownloaded(file_inner_path, hash_id):
                        back["num_optional_removed"] += 1
                        self.log.debug("[OPTIONAL MISSING] %s" % file_inner_path)
                        self.site.content_manager.optionalRemoved(file_inner_path, hash_id, file_node["size"])
                    if add_optional and self.site.isDownloadable(file_inner_path):
                        self.log.debug("[OPTIONAL ADDING] %s" % file_inner_path)
                        bad_files.append(file_inner_path)
                    continue

                if quick_check:
                    ok = os.path.getsize(file_path) == content["files_optional"][file_relative_path]["size"]
                else:
                    try:
                        ok = self.site.content_manager.verifyFile(file_inner_path, open(file_path, "rb"))
                    except Exception as err:
                        ok = False

                if ok:
                    if not self.site.content_manager.isDownloaded(file_inner_path, hash_id):
                        back["num_optional_added"] += 1
                        self.site.content_manager.optionalDownloaded(file_inner_path, hash_id, file_node["size"])
                        optional_added += 1
                        self.log.debug("[OPTIONAL FOUND] %s" % file_inner_path)
                else:
                    if self.site.content_manager.isDownloaded(file_inner_path, hash_id):
                        back["num_optional_removed"] += 1
                        self.site.content_manager.optionalRemoved(file_inner_path, hash_id, file_node["size"])
                        optional_removed += 1
                    bad_files.append(file_inner_path)
                    self.log.debug("[OPTIONAL CHANGED] %s" % file_inner_path)

            if config.verbose:
                self.log.debug(
                    "%s verified: %s, quick: %s, optionals: +%s -%s" %
                    (content_inner_path, len(content["files"]), quick_check, optional_added, optional_removed)
                )

        self.site.content_manager.contents.db.processDelayed()
        time.sleep(0.001)  # Context switch to avoid gevent hangs
        return back

    # Check and try to fix site files integrity
    def updateBadFiles(self, quick_check=True):
        s = time.time()
        res = self.verifyFiles(
            quick_check,
            add_optional=True,
            add_changed=not self.site.settings.get("own")  # Don't overwrite changed files if site owned
        )
        bad_files = res["bad_files"]
        self.site.bad_files = {}
        if bad_files:
            for bad_file in bad_files:
                self.site.bad_files[bad_file] = 1
        self.log.debug("Checked files in %.2fs... Found bad files: %s, Quick:%s" % (time.time() - s, len(bad_files), quick_check))

    # Delete site's all file
    def deleteFiles(self):
        self.log.debug("Deleting files from content.json...")
        files = []  # Get filenames
        for content_inner_path in list(self.site.content_manager.contents.keys()):
            content = self.site.content_manager.contents.get(content_inner_path, {})
            files.append(content_inner_path)
            # Add normal files
            for file_relative_path in list(content.get("files", {}).keys()):
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to site dir
                files.append(file_inner_path)
            # Add optional files
            for file_relative_path in list(content.get("files_optional", {}).keys()):
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to site dir
                files.append(file_inner_path)

        if self.isFile("dbschema.json"):
            self.log.debug("Deleting db file...")
            self.closeDb()
            self.has_db = False
            try:
                schema = self.loadJson("dbschema.json")
                db_path = self.getPath(schema["db_file"])
                if os.path.isfile(db_path):
                    os.unlink(db_path)
            except Exception as err:
                self.log.error("Db file delete error: %s" % err)

        for inner_path in files:
            path = self.getPath(inner_path)
            if os.path.isfile(path):
                for retry in range(5):
                    try:
                        os.unlink(path)
                        break
                    except Exception as err:
                        self.log.error("Error removing %s: %s, try #%s" % (inner_path, err, retry))
                    time.sleep(float(retry) / 10)
            self.onUpdated(inner_path, False)

        self.log.debug("Deleting empty dirs...")
        for root, dirs, files in os.walk(self.directory, topdown=False):
            for dir in dirs:
                path = os.path.join(root, dir)
                if os.path.isdir(path) and os.listdir(path) == []:
                    os.rmdir(path)
                    self.log.debug("Removing %s" % path)
        if os.path.isdir(self.directory) and os.listdir(self.directory) == []:
            os.rmdir(self.directory)  # Remove sites directory if empty

        if os.path.isdir(self.directory):
            self.log.debug("Some unknown file remained in site data dir: %s..." % self.directory)
            return False  # Some files not deleted
        else:
            self.log.debug("Site data directory deleted: %s..." % self.directory)
            return True  # All clean
