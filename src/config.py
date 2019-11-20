from sys import platform

version = '5.7.7'

# The corresponding version of _pytransform.so
core_version = 'r6.0.1'

version_info = '''
PyArmor is a command line tool used to obfuscate python scripts, bind
obfuscated scripts to fixed machine or expire obfuscated scripts.

For more information, refer to https://pyarmor.readthedocs.io
'''

purchase_info = '''

If there is no registration code yet, please purchase one by visiting

https://order.shareit.com/cart/add?vendorid=200089125&PRODUCT[300871197]=1

'''

dll_name = '_pytransform'
dll_ext = '.dylib' if platform == 'darwin' \
    else '.dll' if platform in ('win32', 'cygwin') else '.so'


entry_lines = 'from %spytransform import pyarmor_runtime\n', \
              'pyarmor_runtime(%s)\n'
protect_code_template = 'protect_code.pt'

config_filename = '.pyarmor_config'
capsule_filename = '.pyarmor_capsule.zip'
license_filename = 'license.lic'
default_output_path = 'dist'
default_manifest_template = 'global-include *.py'

platform_urls = [
    'https://github.com/dashingsoft/pyarmor-core/raw/%s/platforms' %
    core_version,
    'https://pyarmor.dashingsoft.com/downloads/latest'
    ]
platform_config = 'index.json'

key_url = 'https://api.dashingsoft.com/product/key/%s/query'
