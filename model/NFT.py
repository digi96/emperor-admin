import json


class NFT:
    tokenType = ''
    tokenId = 0
    name = ''
    imageUrl = ''
    description = ''
    address = ''
    traits = {}

    def __init__(self, tokenType, tokenId, name, imageUrl, description, address, traits):
        self.tokenType = tokenType
        self.tokenId = tokenId
        self.name = name
        self.imageUrl = imageUrl
        self.description = description
        self.address = address
        self.traits = traits
