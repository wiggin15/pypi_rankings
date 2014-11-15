import types
import setuptools, distutils.core, mock
import os
import sys
import shutil
import subprocess

required = None
def setup_mock(*args, **kwargs):
    global required
    required = kwargs.get("install_requires", [])
    if required is None:
        required = []
    if isinstance(required, (set, tuple, types.GeneratorType, dict)):
        required = list(required)
    if isinstance(required, basestring):
        required = required.strip().split('\n')
    if not isinstance(required, list):
        required = None

# Note: this must not be inside a function otherwise global/local lookup will be off
# See: http://bugs.python.org/issue16781
with mock.patch.object(setuptools, "setup", setup_mock), \
     mock.patch.object(distutils.core, "setup", setup_mock), \
     mock.patch.object(sys, "exit"), \
     mock.patch.object(os, "_exit"), \
     mock.patch.object(os, "system"), \
     mock.patch.object(os, "rename"), \
     mock.patch.object(os, "remove"), \
     mock.patch.object(os, "mkdir"), \
     mock.patch.object(os, "makedirs"), \
     mock.patch.object(shutil, "rmtree"), \
     mock.patch.object(shutil, "move"), \
     mock.patch.object(shutil, "copy"), \
     mock.patch.object(shutil, "copyfile"), \
     mock.patch.object(subprocess, "Popen"):
        execfile("setup.py")

print
print repr(required)
