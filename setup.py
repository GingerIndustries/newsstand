import distutils.core
import subprocess

with open("README.md", "r") as fh:
    long_description = fh.read()

packageData = {
        'name': 'newsstand',
        'description': 'NewsStand: News for humans by humans',
        'long_description': long_description,
        'author': 'Ginger Industries',
        'python_requires': '>=3.6',
        'classifiers': [
            "Development Status :: 3 - Alpha",
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        'data_files':[
            ("/usr/share/applications", ["install_data/NewsStand.desktop"]),
            ("/usr/share/mime/packages", ["install_data/newsstand.xml"]),
            ("/usr/local/lib/newsstand/media", ["install_data/media/notify.mp3", "install_data/media/content-loading.gif"]),
            ("/usr/local/lib/newsstand/config", ["install_data/config/sources.nssl", "install_data/config/settings.cfg"])
        ],
        'scripts': [
            'newsstand/newsstand.py'
        ],
        'url': "https://github.com/GingerIndustries/newsstand",
        "package_dir": {
            "newsstand": "newsstand",
            "feedfinder": "newsstand/feedfinder",
            "openutils": "newsstand/openutils"
        },
        'packages': ["newsstand", "feedfinder", "openutils"]
}
distutils.core.setup(**packageData)
print("Configuring permissions for /usr/local/lib/newsstand...")
subprocess.run(["chmod", "--verbose", "-R", "1777", "/usr/local/lib/newsstand"])
print("Refreshing MIME cache...\nThis WILL take a while, so be patient!")
subprocess.run(["update-mime-database", "/usr/share/mime"])
print("Finished!")
