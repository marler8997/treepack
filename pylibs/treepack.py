import sys
import os
import errno
import enum
import util
import loggy

CONFIG_BASENAME = "treepack.config"
DEPSFILE_BASENAME = "treepack.deps"

def is_treepack_repo(path):
    return os.path.isfile(os.path.join(path, CONFIG_BASENAME))

def enforce_is_treepack_repo(path):
    if not is_treepack_repo(path):
        sys.exit("Error: '%s' is not a treepack repo, missing '%s'" % (path, CONFIG_BASENAME))

def get_treepack_root():
    next = os.getcwd()
    while True:
        treepack_file = os.path.join(next, CONFIG_BASENAME)
        if os.path.isfile(treepack_file):
            return next
        temp = os.path.dirname(next)
        if next == temp:
            return None
        next = temp

def get_package_dir(repo, package_name):
    return os.path.join(repo, "packs", package_name)

def new_anon_package(repo):
    next_index = 0
    while True:
        name = str(next_index)
        dir = get_package_dir(repo, name)
        try:
            os.mkdir(dir)
            return name,dir
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        next_index += 1

class TreepackConfig:
    def __init__(self, repo):
        self.repo = repo
        self.config = os.path.join(repo, CONFIG_BASENAME)
        self.line_number = 0
        with open(self.config, "r") as file:
            while True:
                self.line_number += 1
                line = file.readline()
                if not line:
                    break;
                self._parse_line(line.rstrip("\n"))
    def _parse_line(self):
        print("TODO: parse this line '%s'" % line)

LEFT_SUPERSET_OF_RIGHT = 1
RIGHT_SUPERSET_OF_LEFT = 2

class TreepackDeps:
    def __init__(self):
        self.dep_map = {}
    def get_deps(self, package):
        result = self.dep_map.get(package)
        return result if result else []
    def get_package_relation(self, left, right):
        print("[DEBUG] get_package_relation of '%s' and '%s'" % (left, right))
        if left in self.dep_map:
            sys.exit("not impl A")
        elif right in self.dep_map:
            sys.exit("not impl B")
        else:
            return None
    def add_dep(self, pkg, dep):
        util.set_append(self.dep_map, pkg, dep)
    def write(self, repo):
        filename = os.path.join(repo, DEPSFILE_BASENAME)
        with open(filename, "w") as file:
            for pkg, deps in self.dep_map.items():
                file.write("%s\n" % pkg)
                for dep in deps:
                    file.write(" %s\n" % dep)
class TreepackDepsParser:
    def __init__(self, repo):
        self.repo = repo
        self.config = os.path.join(repo, DEPSFILE_BASENAME)
        self.deps = TreepackDeps()
        self.current_package_name = None
        if os.path.exists(self.config):
            self.line_number = 0
            with open(self.config, "r") as file:
                while True:
                    self.line_number += 1
                    line = file.readline()
                    if not line:
                        break;
                    self._parse_line(line.rstrip("\n"))
            self._finish_package()
    def _finish_package(self):
        if self.current_package_name != None:
            self.deps.dep_map[self.current_package_name] = self.current_package_list
            self.current_package_name = None
            self.current_package_list = None
    def _error(self, msg):
        sys.exit("Error: %s(%s) %s" % (self.config, self.line_number, msg))
    def _parse_line(self, line):
        if line.startswith(" "):
            if self.current_package_name == None:
                self._error("found package dep (begins with space ' ') without a package")
            self.current_package_list.append(line[1:])
        else:
            self._finish_package()
            self.current_package_name = line
            self.current_package_list = []
def parse_package_deps(repo):
    parser = TreepackDepsParser(repo)
    return parser.deps

def peel(line):
    space_index = line.find(" ")
    if space_index == -1:
        return line,None
    else:
        return line[0:space_index], line[space_index + 1:]

def mkdirs(dir):
    if os.path.exists(dir):
        return
    parent = os.path.dirname(dir)
    if parent == dir:
        sys.exit("Error: root '%s' does not exist" % parent)
    mkdirs(parent)
    print("mkdir '%s'" % dir)
    os.mkdir(dir)
def copy_file(src, dst):
    mkdirs(os.path.dirname(dst))
    # instead of copying the file...log this operation so we can do it later
    print("copy '%s' to '%s'" % (src, dst))
    loggy.copyfileAndMode(src, dst)


def install_file(source, repo, package, file):
    #print("[DEBUG] install '%s' to package '%s'" % (file, package))
    srcfile = os.path.join(source, file)
    if not os.path.exists(srcfile):
        sys.exit("Error: source file '%s' does not exist" % srcfile)
    repo_package_path = os.path.join(repo, "packs", package)
    dstpath = os.path.join(repo_package_path, os.path.dirname(file))
    mkdirs(dstpath)
    dstfile = os.path.join(repo_package_path, file)
    copy_file(srcfile, dstfile)

def install_link(repo, package, file, link_target):
    repo_package_path = os.path.join(repo, "packs", package)
    dstpath = os.path.join(repo_package_path, os.path.dirname(file))
    mkdirs(dstpath)
    dstfile = os.path.join(repo_package_path, file)
    loggy.enable = True
    loggy.symlink(link_target, dstfile)

def cleandir(packs_dir, dir):
    while True:
        if len(dir) <= len(packs_dir) or len(os.listdir(dir)) > 0:
            return
        print("rmdir '%s'" % dir)
        os.rmdir(dir)
        dir = os.path.dirname(dir)

def move_owner(packs_dir, old_package_dir, new_package_dir, file):
    old = os.path.join(old_package_dir, file)
    new = os.path.join(new_package_dir, file)
    mkdirs(os.path.dirname(new))
    print("rename '%s' to '%s'" % (old, new))
    os.rename(old, new)
    cleandir(packs_dir, os.path.dirname(old))

class Operation:
    def __init__(self, filename):
        self.filename = filename
        self.newpackage = None
        self.source = None
        self.ops_by_package = []
    def finish(self):
        if self.newpackage == None:
            sys.exit("Error: operation does not contain a 'newpackage' directive")
        if self.source == None:
            sys.exit("Error: operation does not contain a 'source' directive")

class PackageOpType(enum.Enum):
    NORMAL = 1
    SPLIT = 2
    SUPERSET = 3

class PackageOp:
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.file_link_tuples = []
    def append(self, file, link_target):
        self.file_link_tuples.append((file, link_target))

class OpParser:
    def __init__(self, repo):
        self.repo = repo
        self.op = Operation(os.path.join(repo, "next_operation"))
        self.line_number = 0
        self.current_package = None
        with open(self.op.filename, "r") as file:
            while True:
                self.line_number += 1
                line = file.readline()
                if not line:
                    break;
                self._parse_line(line.rstrip("\n"))
        self._finish_package()
        self.op.finish()
    def _finish_package(self):
        if self.current_package != None:
            self.op.ops_by_package.append(self.current_package)
            self.current_package = None
    def _error(self, msg):
        sys.exit("Error: %s(%s) %s" % (self.op.filename, self.line_number, msg))
    def _parse_line(self, line):
        if line.startswith(" "):
            if self.current_package == None:
                self._error("cannot install file '%s', package is not set" % file)
            file = line[1:]
            link_index = file.find(" -> ")
            if link_index != -1:
                link_target = file[link_index + 4:]
                file = file[:link_index]
            else:
                link_target = None
            self.current_package.append(file, link_target)
        else:
            directive, rest = peel(line)
            if directive == "newpackage":
                if self.op.newpackage != None:
                    self._error("found multiple 'newpackage' directives")
                self.op.newpackage = line[11:]
                #print("[DEBUG] newpackage '%s'" % self.op.newpackage)
            elif directive == "source":
                if self.op.source != None:
                    self._error("found multiple 'source' directives")
                self.op.source = line[7:]
                #print("[DEBUG] source '%s'" % self.op.source)
            elif directive == "package":
                self._finish_package()
                self.current_package = PackageOp(line[8:], PackageOpType.NORMAL)
                #print("[DEBUG] package '%s'" % self.current_package.name)
            elif directive == "split":
                self._finish_package()
                self.current_package = PackageOp(line[6:], PackageOpType.SPLIT)
                #print("[DEBUG] split '%s'" % self.current_package.name)
            elif directive == "superset":
                self._finish_package()
                self.current_package = PackageOp(line[9:], PackageOpType.SUPERSET)
                #print("[DEBUG] superset '%s'" % self.current_package.name)
            else:
                self._error("unknown directive '%s'" % directive)

def parse_next_operation(repo):
    parser = OpParser(repo)
    return parser.op

def execute_next_op(repo, deps):
    op = parse_next_operation(repo)
    packs_dir = os.path.join(repo, "packs")
    for package_op in op.ops_by_package:
        if package_op.type == PackageOpType.NORMAL:
            for file, link_target in package_op.file_link_tuples:
                if link_target == None:
                    install_file(op.source, repo, package_op.name, file)
                else:
                    install_link(repo, package_op.name, file, link_target)
        elif package_op.type == PackageOpType.SPLIT:
            new_package,new_package_dir = new_anon_package(repo)
            print("[DEBUG] new anonymous package '%s'" % new_package_dir)
            old_package_dir = get_package_dir(repo, package_op.name)
            for file, link_target in package_op.file_link_tuples:
                move_owner(packs_dir, old_package_dir, new_package_dir, file)
            deps.add_dep(package_op.name, new_package)
            deps.add_dep(op.newpackage, new_package)
        else:
            assert package_op.type == PackageOpType.SUPERSET
            old_package_dir = get_package_dir(repo, package_op.name)
            new_package_dir = get_package_dir(repo, op.newpackage)
            for file, link_target in package_op.file_link_tuples:
                move_owner(packs_dir, old_package_dir, new_package_dir, file)
            deps.add_dep(package_op.name, op.newpackage)
    deps.write(repo)
    loggy.remove(op.filename)
