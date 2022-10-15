"""interact - Web3 Helper"""
from asyncio.log import logger
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import config as config
import sys
from solcx import compile_files
import requests
from model.NFT import NFT

w3 = Web3(Web3.HTTPProvider(config.web3HttpProvider))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)


f = open('./abi/emperor-abi.json')
emperorABI = json.load(f)
f.close()

f = open('./abi/emperorfusion-abi.json')
emperorFusionABI = json.load(f)
f.close()

f = open('./abi/marketplace-abi.json')
marketplaceABI = json.load(f)
f.close()

#print(emperorABI, file=sys.stderr)

emperorContract_instance = w3.eth.contract(
    address=config.emperorContractAddress, abi=emperorABI)

emperorFusionContract_instance = w3.eth.contract(
    address=config.emperorFusionContractAddress, abi=emperorFusionABI)

marketplaceContract_instance = w3.eth.contract(
    address=config.marketContractAddress, abi=marketplaceABI)


def getListings():
    listings = marketplaceContract_instance.functions.getUnsoldListings().call()
    #print(listings, file=sys.stderr)
    listingsArr = []
    dummyNFT = {}
    dummyNFT['name'] = 'test'
    dummyNFT['imageUrl'] = 'https://ipfs.digi96.com/ipfs/bafybeiaijl4ztlpkrfe443duhs2chki7ggtr4adcjrvob6ntas7lf5t2lm'
    dummyNFT['description'] = 'test'

    # get all nft in this contract from alchemy
    nfts = getOwnedNFTs(config.marketContractAddress)
    
    for listing in listings:
        vals = {}
        vals['listingId'] = listing[0]
        vals['tokenId'] = listing[2]
        vals['price'] = w3.fromWei(listing[3], 'ether')
        vals['listingType'] = listing[6]  # 0: Primary 1: Secondary
        
        nftTemp = None
        #vals['nft'] = next(nft for nft in nfts if nft.tokenType=='ERC' nft.tokenId == listing[1])
        for nft in nfts:
            if listing[1] == 0:
                if nft.tokenType=='ERC721' and nft.tokenId == listing[2]:
                    nftTemp = nft
                    break

            if listing[1] == 1:
                if nft.tokenType=='ERC1155' and nft.tokenId == listing[2]:
                    nftTemp = nft
                    break

        if nftTemp is not None:
            vals['nft'] = nftTemp
            listingsArr.append(vals)
        else:
            print('NFT not found,listing id:'+ str(listing[0])+ ', tokenId:'+ str(listing[2]))
            
    return listingsArr


def getListingById(id):
    listings = marketplaceContract_instance.functions.getUnsoldListings().call()
    #print(listings, file=sys.stderr)
    listingResult = None

    # get all nft in this contract from alchemy
    nfts = getOwnedNFTs(config.marketContractAddress)
    #print(nfts[1].tokenType)

    for listing in listings:
        if listing[0] == int(id):

            nftTemp = None
            #vals['nft'] = next(nft for nft in nfts if nft.tokenType=='ERC' nft.tokenId == listing[1])
            for nft in nfts:
                if listing[1] == 0:
                    if nft.tokenType=='ERC721' and nft.tokenId == listing[2]:
                        nftTemp = nft
                        break

                if listing[1] == 1:
                    if nft.tokenType=='ERC1155' and nft.tokenId == listing[2]:
                        nftTemp = nft
                        break

            listingResult = {}
            listingResult['listingId'] = listing[0]
            listingResult['tokenId'] = listing[2]
            listingResult['nft'] = nftTemp
            listingResult['price'] = w3.fromWei(listing[3], 'ether')
            # 0: Primary 1: Secondary
            listingResult['listingType'] = listing[6]
            break
    
    #print(listingResult)

    return listingResult


def purchaseListing(id):
    try:
        contract_owner_address = config.contractOwnerAddress
        nonce = w3.eth.get_transaction_count(contract_owner_address)
        listing = getListingById(id)
        if listing is None:
            raise Exception('Provide none eixsting listing id')

        if listing['listingType'] != 0:
            raise Exception('Provide none primary market listing')

        #print(listing, file=sys.stdout)
        print("Transfer to ", config.nftKeeperAddress)

        marketplace_txn = marketplaceContract_instance.functions.purchase(id,
                                                                          config.nftKeeperAddress).buildTransaction({
                                                                              'chainId': 80001,
                                                                              'gas': 10000000,
                                                                              'maxFeePerGas': w3.toWei('2', 'gwei'),
                                                                              'maxPriorityFeePerGas': w3.toWei('1', 'gwei'),
                                                                              'value': w3.toHex(listing['price']),
                                                                              'nonce': nonce,
                                                                          })

        private_key = config.privateKey
        signed_txn = w3.eth.account.sign_transaction(
            marketplace_txn, private_key=private_key)
        print(signed_txn.hash, file=sys.stdout)
        w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print(w3.toHex(w3.keccak(signed_txn.rawTransaction)), file=sys.stdout)

        return w3.toHex(w3.keccak(signed_txn.rawTransaction))
    except Exception as e:
        print(e, file=sys.stderr)
        raise e


def getTransactionReceipt(txHash):
    try:
        receipt = w3.eth.get_transaction_receipt(txHash)
        print(receipt, file=sys.stdout)
        print(type(receipt))
        vals = {}
        vals['status'] = receipt.status
        vals['transactionHash'] = w3.toHex(receipt.transactionHash)
        vals['to'] = receipt.to

        return vals
    except Exception as e:
        errStr = "failed to get receipt for tx: %s, exception: %s" % (
            txHash, e)
        print(errStr, file=sys.stderr)
        return None


def createPayment(title, paymentAddresses, shares):
    try:

        contract_owner_address = config.contractOwnerAddress
        nonce = w3.eth.get_transaction_count(contract_owner_address)
        for address in paymentAddresses:
            if not w3.isAddress(address):
                raise Exception('address is not valid,', address)

        totalShare = 0
        for share in shares:
            totalShare += share

        if len(paymentAddresses) != len(shares):
            raise Exception('paymetn and sale should be paired')

        if totalShare != 100:
            raise Exception('share setting should be 100 in total')

        f = open('./abi/payment-bytecode')
        bytecode = f.read()
        f.close()

        f = open('./abi/payment-abi.json')
        abi = json.load(f)
        f.close()

        print(paymentAddresses, file=sys.stdout)
        print(shares, file=sys.stdout)

        Payment = w3.eth.contract(abi=abi, bytecode=bytecode)
        payment_txn = Payment.constructor(title, paymentAddresses, shares).buildTransaction(
            {
                'from': contract_owner_address,
                'nonce': nonce
            }
        )
        tx_create = w3.eth.account.sign_transaction(
            payment_txn, config.privateKey)

        tx_hash = w3.eth.send_raw_transaction(tx_create.rawTransaction)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        return tx_receipt.contractAddress

    except Exception as e:
        print(e, file=sys.stderr)
        raise e


def getPaymentByAddress(address):
    f = open('./abi/payment-abi.json')
    abi = json.load(f)
    f.close()
    paymentInstance = w3.eth.contract(address=address, abi=abi)
    return paymentInstance


def releasePayment(contractAddress, releaseAddress):
    f = open('./abi/payment-abi.json')
    abi = json.load(f)
    f.close()
    paymentInstance = w3.eth.contract(address=contractAddress, abi=abi)
    contract_owner_address = config.contractOwnerAddress
    nonce = w3.eth.get_transaction_count(contract_owner_address)

    payment_txn = paymentInstance.functions.release(releaseAddress).buildTransaction({
        'chainId': 80001,
        'gas': 10000000,
        'maxFeePerGas': w3.toWei('2', 'gwei'),
        'maxPriorityFeePerGas': w3.toWei('1', 'gwei'),
        'nonce': nonce,
    })

    private_key = config.privateKey
    signed_txn = w3.eth.account.sign_transaction(
        payment_txn, private_key=private_key)
    #print(signed_txn.hash, file=sys.stdout)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    #print(w3.toHex(w3.keccak(signed_txn.rawTransaction)), file=sys.stdout)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(tx_receipt, file=sys.stdout)
    print(type(tx_receipt))
    vals = {}
    vals['status'] = tx_receipt.status
    vals['transactionHash'] = w3.toHex(tx_receipt.transactionHash)
    vals['to'] = tx_receipt.to

    return vals


def createListing(tokenType, tokenId, price, paymentSplitterAddress):
    try:
        contract_owner_address = config.contractOwnerAddress
        nonce = w3.eth.get_transaction_count(contract_owner_address)
        priceWei = w3.toWei(price, 'ether')

        tokenTypeID = 0

        if tokenType == 'ERC721':
            tokenTypeID = 0
        elif tokenType == 'ERC1155':
            tokenTypeID = 1
        else:
            raise Exception('Wrong token type provided')

        marketplace_txn = marketplaceContract_instance.functions.createPrimaryListing(tokenTypeID,
            int(tokenId), priceWei, paymentSplitterAddress).buildTransaction({
                'chainId': 80001,
                'gas': 10000000,
                'maxFeePerGas': w3.toWei('2', 'gwei'),
                'maxPriorityFeePerGas': w3.toWei('1', 'gwei'),
                'nonce': nonce,
            })

        private_key = config.privateKey
        signed_txn = w3.eth.account.sign_transaction(
            marketplace_txn, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print(tx_hash, file=sys.stdout)
        # tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        # print(tx_receipt, file=sys.stdout)
        # print(type(tx_receipt))
        # vals = {}
        # vals['status'] = tx_receipt.status
        # vals['transactionHash'] =w3.toHex(tx_receipt.transactionHash)
        # vals['to'] = tx_receipt.to

        # return vals
        return w3.toHex(w3.keccak(signed_txn.rawTransaction))

    except Exception as e:
        print(e, file=sys.stderr)
        raise e


def getBalanceOfAddress(address):
    return w3.fromWei(w3.eth.getBalance(address), 'ether')


def getOwnedNFTs(ownerAddress):
    urlGet = config.web3HttpProvider + '/getNFTs/?owner='+ownerAddress +\
        '&contractAddresses[]=' + config.emperorContractAddress + "&contractAddresses[]=" +\
        config.emperorFusionContractAddress
    #print(urlGet, file=sys.stdout)
    contentResult = json.loads(requests.get(urlGet).content)
    #print(contentResult, file=sys.stdout)

    nftsReturn = []
    for nftTemp in contentResult['ownedNfts']:
        #print(nftTemp['metadata'])
        nftName = 'N/A'
        nftImage = 'https://ipfs.digi96.com/ipfs/QmcsRmpwMUBqfVq6wq4zTCQA3ATHDp8bcyLigrmoEikTio'
        nftDescription = 'N/A'
        if "name" in nftTemp['metadata']:
            nftName = nftTemp['metadata']['name']
            nftImage = nftTemp['metadata']['image'].replace('gateway.pinata.cloud',
                                                            'ipfs.digi96.com')
            nftDescription = nftTemp['metadata']['description']

        nft = NFT(nftTemp['id']['tokenMetadata']['tokenType'], int(nftTemp['id']['tokenId'], 16),
                  nftName, nftImage, nftDescription, nftTemp['contract']['address'], nftTemp['metadata']['traits'])
        nftsReturn.append(nft)

    #print(nftsReturn, file=sys.stdout)
    return nftsReturn


def getNFTByTokenId(tokenType, tokenId):
    # get tokenUri
    tokenUri = ""
    address = ""
    if tokenType == "ERC721":
        tokenUri = emperorContract_instance.functions.tokenURI(tokenId).call()
        address = config.emperorContractAddress 
    else:
        tokenUri = emperorFusionContract_instance.functions.uri(tokenId).call()
        address = config.emperorFusionContractAddress

    # get metadata from pinata
    jsonR = json.loads(requests.get(tokenUri.replace('gateway.pinata.cloud',
                                                     'ipfs.digi96.com')).content)
    nft = NFT(tokenType, tokenId, jsonR['name'], jsonR['image'].replace('gateway.pinata.cloud',
                                                                        'ipfs.digi96.com'), jsonR['description'], address, jsonR['traits'])
    return nft


def mintNFT(amount, metadataUri):
    contract_owner_address = config.contractOwnerAddress
    nonce = w3.eth.get_transaction_count(contract_owner_address)

    mint_txn = None

    print('mint amount:' + str(amount))

    if amount==1:
        print('mint ERC721')
        mint_txn = emperorContract_instance.functions.mintNFT(contract_owner_address,
                                                             metadataUri).buildTransaction({
                                                                 'chainId': 80001,
                                                                 'gas': 10000000,
                                                                 'maxFeePerGas': w3.toWei('2', 'gwei'),
                                                                 'maxPriorityFeePerGas': w3.toWei('1', 'gwei'),
                                                                 'nonce': nonce,
                                                             })
    else:
        print('mint ERC1155')
        mint_txn = emperorFusionContract_instance.functions.mintNFT(contract_owner_address, amount,
                                                             metadataUri).buildTransaction({
                                                                 'chainId': 80001,
                                                                 'gas': 10000000,
                                                                 'maxFeePerGas': w3.toWei('2', 'gwei'),
                                                                 'maxPriorityFeePerGas': w3.toWei('1', 'gwei'),
                                                                 'nonce': nonce,
                                                             })

    private_key = config.privateKey
    signed_txn = w3.eth.account.sign_transaction(
        mint_txn, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print(tx_hash, file=sys.stdout)
    #tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    #print(tx_receipt, file=sys.stdout)
    # print(type(tx_receipt))
    #vals = {}
    #vals['status'] = tx_receipt.status
    #vals['transactionHash'] = w3.toHex(tx_receipt.transactionHash)
    #vals['to'] = tx_receipt.to

    # return vals
    return w3.toHex(w3.keccak(signed_txn.rawTransaction))


def getTransactionReceipt(txHash):
    try:
        receipt = w3.eth.get_transaction_receipt(txHash)
        return receipt
    except Exception as e:
        # <class 'web3.exceptions.TransactionNotFound'>
        print(type(e))
        print('Unknow error', e)
        return None

def getERC115TokenBalance(tokenId):
    try:
        tokenBalance = emperorFusionContract_instance.functions.balanceOf(config.contractOwnerAddress, tokenId).call()
        return tokenBalance

    except Exception as e:
        print(e)
        return 0

def delistListing(listingId):
    try:
        contract_owner_address = config.contractOwnerAddress
        nonce = w3.eth.get_transaction_count(contract_owner_address)
        
        
        marketplace_txn = marketplaceContract_instance.functions.deListing(listingId).buildTransaction({
                'chainId': 80001,
                'gas': 10000000,
                'maxFeePerGas': w3.toWei('2', 'gwei'),
                'maxPriorityFeePerGas': w3.toWei('1', 'gwei'),
                'nonce': nonce,
            })

        private_key = config.privateKey
        signed_txn = w3.eth.account.sign_transaction(
            marketplace_txn, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print(tx_hash, file=sys.stdout)
        
        return w3.toHex(w3.keccak(signed_txn.rawTransaction))

    except Exception as e:
        print(e, file=sys.stderr)
        raise e