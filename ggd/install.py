#-------------------------------------------------------------------------------------------------------------
## Import Statements
#-------------------------------------------------------------------------------------------------------------
from __future__ import print_function 
import sys
import os
import subprocess as sp
import glob
from .check_recipe import conda_root
from .utils import get_species
from .utils import get_ggd_channels
from .utils import get_channel_data
from .utils import get_channeldata_url
from .search import load_json, load_json_from_url, search_packages
from .uninstall import remove_from_condaroot, check_for_installation

SPECIES_LIST = get_species()
#-------------------------------------------------------------------------------------------------------------
## Argument Parser
#-------------------------------------------------------------------------------------------------------------
def add_install(p):
    c = p.add_parser('install', help="install a data recipe from ggd")
    c.add_argument("-c", "--channel", default="genomics", choices=get_ggd_channels(), 
                     help="The ggd channel the desired recipe is stored in. (Default = genomics)")
    c.add_argument("-v", "--version", default="-1", help="A specific ggd package version to install. If the -v flag is not used the latest version will be installed.")
    c.add_argument("name", help="the name of the recipe to install")
    c.set_defaults(func=install)

#-------------------------------------------------------------------------------------------------------------
## Functions/Methods
#-------------------------------------------------------------------------------------------------------------


# check_ggd_recipe
# ================
# Method to check if the ggd recipe exists. Uses searc_packages from search.py to 
#  search the ggd-channel json file. If the recipe exists within the json file,
#  the installation proceeds. If not, the instalation stops
def check_ggd_recipe(ggd_recipe,ggd_channel):
    CHANNEL_DATA_URL = get_channeldata_url(ggd_channel)
    jdict = load_json_from_url(CHANNEL_DATA_URL)
    package_list = [x[0] for x in search_packages(jdict, ggd_recipe)]
    if ggd_recipe in package_list:
        print("\n\t-> %s exists in the ggd-%s channel" %(ggd_recipe,ggd_channel))
        return(jdict)
    else:
        print("\n\t-> '%s' was not found in ggd-%s" %(ggd_recipe, ggd_channel))
        print("\t-> You can search for recipes using the ggd search tool: \n\t\t'ggd search -t %s'\n" %ggd_recipe)
        sys.exit()


# check_if_installed
# =================
# Method to check if the recipe has already been installed and is in 
#  the conda ggd storage path. If it is already installed the installation stops.
def check_if_installed(ggd_recipe,ggd_jdict,ggd_version):
    species = ggd_jdict["packages"][ggd_recipe]["identifiers"]["species"]
    build = ggd_jdict["packages"][ggd_recipe]["identifiers"]["genome-build"]
    version = ggd_jdict["packages"][ggd_recipe]["version"]

    CONDA_ROOT = conda_root()
    path = os.path.join(CONDA_ROOT,"share","ggd",species,build,ggd_recipe,version)
    recipe_exists = glob.glob(path)
    if recipe_exists:
        # if the ggd_version designated to be installed does not match the installed version, install the designated version
        if ggd_version != version and ggd_version != "-1":
            return(False)
        else:
            print("\n\t-> '%s' is already installed." %ggd_recipe)
            print("\t-> You can find %s here: %s" %(ggd_recipe,path))
            sys.exit()
    else:
        print("\n\t-> %s is not installed on your system" %ggd_recipe)
        return(False)
    

# check_conda_installation
# =======================
# Method used to check if the recipe has been installed using conda. 
def check_conda_installation(ggd_recipe,ggd_version):
    conda_package_list = sp.check_output(["conda", "list"]).decode('utf8')
    recipe_find = conda_package_list.find(ggd_recipe)
    if recipe_find == -1:
        print("\n\t-> %s has not been installed by conda" %ggd_recipe)
        return(False)
    elif ggd_version != "-1": ## Check if ggd version was designated 
        installed_version = conda_package_list[recipe_find:recipe_find+100].split("\n")[0].replace(" ","")[len(ggd_recipe)]
        if installed_version != ggd_version:
            print("\n\t-> %s version %s has not been installed by conda" %(ggd_recipe,str(ggd_version)))
            return(False)
        else:
            print("\n\t-> %s version %s has been installed by conda on your system and must be uninstalled to proceed." %(ggd_recipe,str(ggd_version)))
            print("\t-> To reinstall run:\n\t\t ggd uninstall %s \n\t\t ggd install %s" %(ggd_recipe,ggd_recipe))
    else:
        print("\n\t-> %s has been installed by conda on your system and must be uninstalled to proceed." %ggd_recipe)
        print("\t-> To reinstall run:\n\t\t ggd uninstall %s \n\t\t ggd install %s" %(ggd_recipe,ggd_recipe))


# check_S3_bucket
# ==============
# Method to check if the recipe is stored on the ggd S3 bucket. If so it installs from S3
def check_S3_bucket(ggd_recipe, ggd_jdict):
    if "tags" in ggd_jdict["packages"][ggd_recipe]:
        if "cached" in ggd_jdict["packages"][ggd_recipe]["tags"]:
            if "uploaded_to_aws" in ggd_jdict["packages"][ggd_recipe]["tags"]["cached"]:
                print("\n\t-> The %s package is uploaded to an aws S3 bucket. To reduce processing time the package will be downloaded from this aws S3 bucket" %ggd_recipe)


# conda_install
# ============
# Method to install the recipe from the ggd-channel using conda
def conda_install(ggd_recipe, ggd_channel,ggd_jdict,ggd_version):
    if ggd_version != "-1":
        print("\n\t-> Installing %s version %s" %(ggd_recipe,ggd_version))
        try:
            sp.check_call(["conda", "install", "-c", "ggd-"+ggd_channel, "-y", ggd_recipe+"="+ggd_version+"*"], stderr=sys.stderr, stdout=sys.stdout)
        except sp.CalledProcessError as e:
            sys.stderr.write("\n\t-> ERROR in install %s\n" %ggd_recipe)
            sys.stderr.write(str(e))
            sys.exit(e.returncode)
    else:
        print("\n\t-> Installing %s" %ggd_recipe)
        try:
            sp.check_call(["conda", "install", "-c", "ggd-"+ggd_channel, "-y", ggd_recipe], stderr=sys.stderr, stdout=sys.stdout)
        except sp.CalledProcessError as e:
            sys.stderr.write("\n\t-> ERROR in install %s\n" %ggd_recipe)
            sys.stderr.write(str(e))
            sys.stderr.write("\n\t-> Removing files created by ggd during installation")
            check_for_installation(ggd_recipe,ggd_jdict) ## .uninstall method to remove extra ggd files
            sys.exit(e.returncode)


# install
# ======
# Main method used to check installation and install the ggd recipe
def install(parser, args):
    print("\n\t-> Looking for %s in the 'ggd-%s' channel" %(args.name,args.channel))
    ## Check if the recipe is in ggd
    ggd_jsonDict = check_ggd_recipe(args.name,args.channel)
    ## Check if the recipe is already installed  
    if not check_if_installed(args.name,ggd_jsonDict,args.version):
        ## Check if conda has it installed on the system 
        if not check_conda_installation(args.name,args.version):
            ## Check S3 bucket if version has not been set
            if args.version != "-1":
                check_S3_bucket(args.name, ggd_jsonDict)
            conda_install(args.name, args.channel, ggd_jsonDict,args.version)
            print("\n\t-> DONE")
                
