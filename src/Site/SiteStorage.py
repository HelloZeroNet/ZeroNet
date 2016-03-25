import os
import re
import shutil
import json
import time
import sys

import sqlite3
import gevent.event

from Db import Db
from Debug import Debug
from Config import config
from util import helper


class SiteStorage:

    def __init__(self, site, allow_create=True):
        self.site = site
        self.directory = "%s/%s" % (config.data_dir, self.site.address)  # Site data diretory
        self.allowed_dir = os.path.abspath(self.directory.decode(sys.getfilesystemencoding()))  # Only serve/modify file within this dir
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

    # Load db from dbschema.json
    def openDb(self, check=True):
        try:
            schema = self.loadJson("dbschema.json")
            db_path = self.getPath(schema["db_file"])
        except Exception, err:
            raise Exception("dbschema.json is not a valid JSON: %s" % err)

        if check:
            if not os.path.isfile(db_path) or os.path.getsize(db_path) == 0:  # Not exist or null
                self.rebuildDb()

        if not self.db:
            self.db = Db(schema, db_path)

        if check and not self.db_checked:
            changed_tables = self.db.checkTables()
            if changed_tables:
                self.rebuildDb(delete_db=False)  # TODO: only update the changed table datas

    def closeDb(self):
        if self.db:
            self.db.close()
        self.event_db_busy = None
        self.db = None

    # Return db class
    def getDb(self):
        if not self.db:
            self.log.debug("No database, waiting for dbschema.json...")
            self.site.needFile("dbschema.json", priority=3)
            self.has_db = self.isFile("dbschema.json")  # Recheck if dbschema exist
            if self.has_db:
                self.openDb()
        return self.db

    # Rebuild sql cache
    def rebuildDb(self, delete_db=True):
        self.has_db = self.isFile("dbschema.json")
        if not self.has_db:
            return False
        self.event_db_busy = gevent.event.AsyncResult()
        schema = self.loadJson("dbschema.json")
        db_path = self.getPath(schema["db_file"])
        if os.path.isfile(db_path) and delete_db:
            if self.db:
                self.db.close()  # Close db if open
            self.log.info("Deleting %s" % db_path)
            try:
                os.unlink(db_path)
            except Exception, err:
                self.log.error("Delete error: %s" % err)
        self.openDb(check=False)
        self.log.info("Creating tables...")
        self.db.checkTables()
        self.log.info("Importing data...")
        cur = self.db.getCursor()
        cur.execute("BEGIN")
        cur.logging = False
        found = 0
        s = time.time()
        for content_inner_path, content in self.site.content_manager.contents.items():
            content_path = self.getPath(content_inner_path)
            if os.path.isfile(content_path):  # Missing content.json file
                if self.db.loadJson(content_path, cur=cur):
                    found += 1
            else:
                self.log.error("[MISSING] %s" % content_inner_path)
            for file_relative_path in content["files"].keys():
                if not file_relative_path.endswith(".json"):
                    continue  # We only interesed in json files
                content_inner_path_dir = helper.getDirname(content_inner_path)  # Content.json dir relative to site
                file_inner_path = content_inner_path_dir + file_relative_path  # File Relative to site dir
                file_inner_path = file_inner_path.strip("/")  # Strip leading /
                file_path = self.getPath(file_inner_path)
                if os.path.isfile(file_path):
                    if self.db.loadJson(file_path, cur=cur):
                        found += 1
                else:
                    self.log.error("[MISSING] %s" % file_inner_path)
        cur.execute("END")
        self.log.info("Imported %s data file in %ss" % (found, time.time() - s))
        self.event_db_busy.set(True)  # Event done, notify waiters
        self.event_db_busy = None  # Clear event

    # Execute sql query or rebuild on dberror
    def query(self, query, params=None):
        if self.event_db_busy:  # Db not ready for queries
            self.log.debug("Wating for db...")
            self.event_db_busy.get()  # Wait for event
        try:
            res = self.getDb().execute(query, params)
        except sqlite3.DatabaseError, err:
            if err.__class__.__name__ == "DatabaseError":
                self.log.error("Database error: %s, query: %s, try to rebuilding it..." % (err, query))
                self.rebuildDb()
                res = self.db.cur.execute(query, params)
            else:
                raise err
        return res

    # Open file object
    def open(self, inner_path, mode="rb"):
        return open(self.getPath(inner_path), mode)

    # Open file object
    def read(self, inner_path, mode="r"):
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
            with open(file_path, "wb") as file:
                file.write(content)
        del content
        self.onUpdated(inner_path)

    # Remove file from filesystem
    def delete(self, inner_path):
        file_path = self.getPath(inner_path)
        os.unlink(file_path)

    def deleteDir(self, inner_path):
        dir_path = self.getPath(inner_path)
        os.rmdir(dir_path)

    # List files from a directory
    def list(self, dir_inner_path):
        directory = self.getPath(dir_inner_path)
        for root, dirs, files in os.walk(directory):
            root = root.replace("\\", "/")
            root_relative_path = re.sub("^%s" % re.escape(directory), "", root).lstrip("/")
            for file_name in files:
                if root_relative_path:  # Not root dir
                    yield root_relative_path + "/" + file_name
                else:
                    yield file_name

    # Site content updated
    def onUpdated(self, inner_path):
        file_path = self.getPath(inner_path)
        # Update Sql cache
        if inner_path == "dbschema.json":
            self.has_db = self.isFile("dbschema.json")
            # Reopen DB to check changes
            self.closeDb()
            self.openDb()
        elif not config.disable_db and inner_path.endswith(".json") and self.has_db:  # Load json file to db
            self.log.debug("Loading json file to db: %s" % inner_path)
            try:
                self.getDb().loadJson(file_path)
            except Exception, err:
                self.log.error("Json %s load error: %s" % (inner_path, Debug.formatException(err)))
                self.closeDb()

    # Load and parse json file
    def loadJson(self, inner_path):
        with self.open(inner_path) as file:
            return json.load(file)

    # Write formatted json file
    def writeJson(self, inner_path, data):
        content = json.dumps(data, indent=1, sort_keys=True)
        # Make it a little more compact by removing unnecessary white space

        def compact_list(match):
            return "[ " + match.group(1).strip() + " ]"

        def compact_dict(match):
            return "{ " + match.group(1).strip() + " }"

        content = re.sub("\[([^,\{\[]{10,100}?)\]", compact_list, content, flags=re.DOTALL)
        content = re.sub("\{([^,\[\{]{10,100}?)\}", compact_dict, content, flags=re.DOTALL)

        # Remove end of line whitespace
        content = re.sub("(?m)[ ]+$", "", content)

        # Write to disk
        self.write(inner_path, content)

    # Get file size
    def getSize(self, inner_path):
        path = self.getPath(inner_path)
        if os.path.isfile(path):
            return os.path.getsize(path)
        else:
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
        inner_path = re.sub("^%s/" % re.escape(self.directory), "", inner_path)  # Remove site directory if begins with it
        file_path = u"%s/%s" % (self.directory, inner_path)
        if not inner_path:
            return self.directory

        file_abspath = os.path.dirname(os.path.abspath(file_path))
        if ".." in file_path or not file_abspath.startswith(self.allowed_dir):
            self.site.log.error(u"File %s not in allowed dir: %s" % (file_path, self.allowed_dir))
            raise Exception(u"File not allowed: %s" % file_path)
        return file_path

    # Get site dir relative path
    def getInnerPath(self, path):
        if path == self.directory:
            inner_path = ""
        else:
            inner_path = re.sub("^%s/" % re.escape(self.directory), "", path)
        return inner_path

    # Verify all files sha512sum using content.json
    def verifyFiles(self, quick_check=False, add_optional=False, add_changed=True):
        bad_files = []
        i = 0

        if not self.site.content_manager.contents.get("content.json"):  # No content.json, download it first
            self.site.needFile("content.json", update=True)  # Force update to fix corrupt file
            self.site.content_manager.loadContent()  # Reload content.json
        for content_inner_path, content in self.site.content_manager.contents.items():
            i += 1
            if i % 50 == 0:
                time.sleep(0.0001)  # Context switch to avoid gevent hangs
            if not os.path.isfile(self.getPath(content_inner_path)):  # Missing content.json file
                self.log.debug("[MISSING] %s" % content_inner_path)
                bad_files.append(content_inner_path)

            for file_relative_path in content.get("files", {}).keys():
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to site dir
                file_inner_path = file_inner_path.strip("/")  # Strip leading /
                file_path = self.getPath(file_inner_path)
                if not os.path.isfile(file_path):
                    self.log.debug("[MISSING] %s" % file_inner_path)
                    bad_files.append(file_inner_path)
                    continue

                if quick_check:
                    ok = os.path.getsize(file_path) == content["files"][file_relative_path]["size"]
                else:
                    ok = self.site.content_manager.verifyFile(file_inner_path, open(file_path, "rb"))

                if not ok:
                    self.log.debug("[CHANGED] %s" % file_inner_path)
                    if add_changed or content.get("cert_sign"):  # If updating own site only add changed user files
                        bad_files.append(file_inner_path)

            # Optional files
            optional_added = 0
            optional_removed = 0
            for file_relative_path in content.get("files_optional", {}).keys():
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to site dir
                file_inner_path = file_inner_path.strip("/")  # Strip leading /
                file_path = self.getPath(file_inner_path)
                if not os.path.isfile(file_path):
                    self.site.content_manager.hashfield.removeHash(content["files_optional"][file_relative_path]["sha512"])
                    if add_optional:
                        bad_files.append(file_inner_path)
                    continue

                if quick_check:
                    ok = os.path.getsize(file_path) == content["files_optional"][file_relative_path]["size"]
                else:
                    ok = self.site.content_manager.verifyFile(file_inner_path, open(file_path, "rb"))

                if ok:
                    self.site.content_manager.hashfield.appendHash(content["files_optional"][file_relative_path]["sha512"])
                    optional_added += 1
                else:
                    self.site.content_manager.hashfield.removeHash(content["files_optional"][file_relative_path]["sha512"])
                    optional_removed += 1
                    if add_optional:
                        bad_files.append(file_inner_path)
                    self.log.debug("[OPTIONAL CHANGED] %s" % file_inner_path)

            if config.verbose:
                self.log.debug(
                    "%s verified: %s, quick: %s, bad: %s, optionals: +%s -%s" %
                    (content_inner_path, len(content["files"]), quick_check, bad_files, optional_added, optional_removed)
                )

        time.sleep(0.0001)  # Context switch to avoid gevent hangs
        return bad_files

    # Check and try to fix site files integrity
    def checkFiles(self, quick_check=True):
        s = time.time()
        bad_files = self.verifyFiles(
            quick_check,
            add_optional=self.site.settings.get("autodownloadoptional"),
            add_changed=not self.site.settings.get("own")  # Don't overwrite changed files if site owned
        )
        self.site.bad_files = {}
        if bad_files:
            for bad_file in bad_files:
                self.site.bad_files[bad_file] = 1
        self.log.debug("Checked files in %.2fs... Found bad files: %s, Quick:%s" % (time.time() - s, len(bad_files), quick_check))

    # Delete site's all file
    def deleteFiles(self):
        if self.has_db:
            self.log.debug("Deleting db file...")
            self.closeDb()
            try:
                schema = self.loadJson("dbschema.json")
                db_path = self.getPath(schema["db_file"])
                if os.path.isfile(db_path):
                    os.unlink(db_path)
            except Exception, err:
                self.log.error("Db file delete error: %s" % err)

        self.log.debug("Deleting files from content.json...")
        files = []  # Get filenames
        for content_inner_path, content in self.site.content_manager.contents.items():
            files.append(content_inner_path)
            # Add normal files
            for file_relative_path in content.get("files", {}).keys():
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to site dir
                files.append(file_inner_path)
            # Add optional files
            for file_relative_path in content.get("files_optional", {}).keys():
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to site dir
                files.append(file_inner_path)

        for inner_path in files:
            path = self.getPath(inner_path)
            if os.path.isfile(path):
                os.unlink(path)

        self.log.debug("Deleting empty dirs...")
        for root, dirs, files in os.walk(self.directory, topdown=False):
            for dir in dirs:
                path = os.path.join(root, dir)
                if os.path.isdir(path) and os.listdir(path) == []:
                    os.removedirs(path)
                    self.log.debug("Removing %s" % path)
        if os.path.isdir(self.directory) and os.listdir(self.directory) == []:
            os.removedirs(self.directory)  # Remove sites directory if empty

        if os.path.isdir(self.directory):
            self.log.debug("Some unknown file remained in site data dir: %s..." % self.directory)
            return False  # Some files not deleted
        else:
            self.log.debug("Site data directory deleted: %s..." % self.directory)
            return True  # All clean
