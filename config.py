from os import environ, path
from dotenv import load_dotenv

basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, '.env'))

web3HttpProvider = environ.get('Web3_HTTP_Provider')
emperorContractAddress = environ.get('Emperor_Contract_Address')
emperorFusionContractAddress = environ.get('EmperorFusion_Contract_Address')
marketContractAddress = environ.get('Marketplace_Contract_Address')
contractOwnerAddress = environ.get('Contract_Owner_Address')
privateKey = environ.get('Contract_Owner_Key')
nftKeeperAddress = environ.get('NFT_Keeper_Address')
pinataJWT = environ.get('Pinata_JWT')
databaseURI = environ.get('DATABASE_URI')
uploadFolder = environ.get('UPLOAD_FOLDER')
