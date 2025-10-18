import argostranslate.package

# Download and install translation packages (only once)
def install_argos_packages():
    packages = argostranslate.package.get_available_packages()
    for lang in ['zh', 'ja', 'ko']:
        for pkg in packages:
            if pkg.from_code == lang and pkg.to_code == 'en':
                download_path = pkg.download()
                argostranslate.package.install_from_path(download_path)
