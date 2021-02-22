import setuptools
import distutils.log
from setuptools.command.install import install
import distutils.cmd
import subprocess

with open("README.md", "r") as fh:
    long_description = fh.read()

class InstallWrapper(install):
    def run(self):
        try:
            subprocess.run(["true"])
        except AttributeError:
            self.announce("ERR: Trying to install with Python 2. Use 'python3' instead of 'python'.", level=distutils.log.FATAL)
        else:
            install.run(self)
            self.postInstall()
    def postInstall(self):
        self.announce("Configuring permissions for /usr/local/lib/newsstand...", level=distutils.log.INFO)
        subprocess.run(["chmod", "--verbose", "-R", "1777", "/usr/local/lib/newsstand"])
        self.announce("Refreshing MIME cache...\nThis WILL take a while, so be patient!", level=distutils.log.INFO)
        subprocess.run(["update-mime-database", "/usr/share/mime"])
        self.announce("Updating .desktop MIME database...", level=distutils.log.INFO)
        subprocess.run(["update-desktop-database", "/usr/share/mime"])
        self.announce("Finished!", level=distutils.log.INFO)

class Uninstall(distutils.cmd.Command):
    description = 'Uninstall NewsStand'
    user_options = [
        ('full-remove', None, 'Remove ALL of NewsStand\'s data.'),
    ]
    def initialize_options(self):
        self.full_remove = None
    def finalize_options(self):
        pass
    def run(self):
        if input("Please confirm that you want to uninstall NewsStand. [Y/N] > ") == "Y":
            self.announce("Removing /usr/local/lib/newsstand", level=distutils.log.INFO)
            subprocess.run(["rm", "-r", "-f", "/usr/local/lib/newsstand"])
            self.announce("Removing desktop files", level=distutils.log.INFO)
            subprocess.run(["rm", "-f", "/usr/share/applications/NewsStand.desktop"])
            self.announce("Removing MIME data", level=distutils.log.INFO)
            subprocess.run(["rm", "-f", "/usr/share/mime/packages/newsstand.xml"])
            if self.full_remove:
                self.announce("Removing install directory", level=distutils.log.WARN)
                subprocess.run(["rm", "-r", "-f", "."])
            self.announce("Refreshing MIME cache\nThis WILL take a while, so be patient.", level=distutils.log.INFO)
            subprocess.run(["update-mime-database", "/usr/share/mime"])
            self.announce("Finished uninstalling NewsStand. I'm sorry you didn't like it. Please, tell me what's wrong on GitHub. Thanks, GingerIndustries", level=distutils.log.INFO)
        else:
            self.announce("Abort.", level=distutils.log.FATAL)
setuptools.setup(
        cmdclass = {"install": InstallWrapper, "uninstall" : Uninstall},
        name = 'newsstand',
        description = 'NewsStand: News for humans by humans',
        long_description = long_description,
        author = 'Ginger Industries',
        python_requires = '>=3.6',
        classifiers = [
            "Development Status :: 3 - Alpha",
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        data_files = [
            ("/usr/share/applications", ["install_data/NewsStand.desktop"]),
            ("/usr/share/mime/packages", ["install_data/newsstand.xml"]),
            ("/usr/local/lib/newsstand/media", ["install_data/media/notify.mp3", "install_data/media/content-loading.gif"]),
            ("/usr/local/lib/newsstand/config", ["install_data/config/sources.nssl", "install_data/config/settings.cfg"])
        ],
        scripts = [
            'newsstand/newsstand.py'
        ],
        url = "https://github.com/GingerIndustries/newsstand",
        package_dir = {
            "newsstand": "newsstand",
            "feedfinder": "newsstand/feedfinder",
            "openutils": "newsstand/openutils"
        },
        packages = ["newsstand", "feedfinder", "openutils"]
)

