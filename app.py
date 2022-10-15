from code import interact
from crypt import methods
from distutils.command.config import config
from email.policy import default
from ensurepip import bootstrap
from telnetlib import STATUS
from flask import Flask, flash, render_template, url_for, request, redirect, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import helper.interact as web3Interact
import json
import logging
import os
import requests
import config as config
from flask_bootstrap import Bootstrap

UPLOAD_FOLDER = config.uploadFolder
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

bootstrap = Bootstrap(app)
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
# mysql+mysqlconnector://<user>:<password>@<host>[:<port>]/<dbname>
app.config['SQLALCHEMY_DATABASE_URI'] = config.databaseURI
db = SQLAlchemy(app)
db.create_all(app=app)


class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return '<Task %r>' % self.id


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    contract_address = db.Column(db.String(100), nullable=True)
    payment_address1 = db.Column(db.String(100), nullable=False)
    payment_address2 = db.Column(db.String(100), nullable=True)
    share1 = db.Column(db.Integer, nullable=False)
    share2 = db.Column(db.Integer, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return '<Payment %r>' % self.id


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        task_content = request.form['content']
        new_task = Todo(content=task_content)

        try:
            db.session.add(new_task)
            db.session.commit()
            return redirect('/')
        except:
            return 'There was in issue adding your task'
    else:
        tasks = Todo.query.order_by(Todo.date_created).all()
        return render_template('index.html', tasks=tasks)


@app.route('/delete/<int:id>')
def delete(id):
    task_to_delete = Todo.query.get_or_404(id)
    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was a problem deleting that task'


@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    task = Todo.query.get_or_404(id)

    if request.method == 'POST':
        task.content = request.form['content']
        try:
            db.session.commit()
            return redirect('/')
        except:
            return 'There was a problem updating that task'
    else:
        return render_template('update.html', task=task)

@app.route('/listings/delisting', methods=['POST'])
def delisting():
    listingId = request.form['listingId']
    print('deleting list id:', listingId)
    try:
        txHash = web3Interact.delistListing(int(listingId))
        print(txHash)
        return redirect(url_for('getTransactionStatus', txHash=txHash))
    except Exception as e:
        return jsonify({
                "status": "failed",
                "data": None,
                "message": str(e)
        })

@app.route('/listings', methods=['GET', 'POST'])
def listings():
    if request.method == 'GET':
        listings = web3Interact.getListings()
        app.logger.info(listings)
        return render_template('listings.html', listings=listings)
    else:
        tokenId = request.form['tokenId']
        tokenType = request.form['tokenType']
        price = request.form['price']
        paymentSplitterAddress = request.form['paymentSplitterAddress']
        try:
            txHash = web3Interact.createListing(tokenType,
                tokenId, price, paymentSplitterAddress)
            print(txHash)
            return redirect(url_for('getTransactionStatus', txHash=txHash))
        except Exception as e:
            return jsonify({
                "status": "failed",
                "data": None,
                "message": str(e)
            }) 


@app.route('/listings/<int:listingId>/purchase', methods=['GET'])
def purchase(listingId):
    # check if listingId valid
    listings = web3Interact.getListings()
    if not any(d['listingId'] == listingId for d in listings):
        return 'listing id not exists', 404
    try:
        txHash = web3Interact.purchaseListing(listingId)

        if txHash is not None:

            return jsonify({
                "status": "ok",
                "data": txHash
            })
        else:
            raise Exception('get null txHash')
    except Exception as e:
        return jsonify({
            "status": "failed",
            "data": None,
            "message": str(e)
        })


@app.route('/transaction/<string:txHash>/receipt', methods=['GET'])
def getTransactionReceipt(txHash):
    receipt = web3Interact.getTransactionReceipt(txHash)
    if receipt is not None:
        return jsonify({"status": "ok", "data": receipt})
    else:
        return jsonify({
            "status": "failed",
            "data": None
        })


@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if request.method == 'POST':
        title = request.form['title']
        address1 = request.form['address1']
        address2 = request.form['address2']
        share1 = request.form['share1']
        share2 = request.form['share2']

        addressArr = []
        addressArr.append(address1)
        if address2 != '':
            addressArr.append(address2)

        shareArr = []
        shareArr.append(int(share1))
        if share2 != '':
            shareArr.append(int(share2))
        else:
            share2 = 0

        contractAddress = web3Interact.createPayment(
            title, addressArr, shareArr)

        new_payment = Payment(title=title, contract_address=contractAddress, payment_address1=address1,
                              payment_address2=address2, share1=share1, share2=share2)

        try:
            db.session.add(new_payment)
            db.session.commit()
            db.session.close()
            return redirect('/payment')
        except Exception as e:
            app.logger.info(e)
            return 'There was in issue adding your payment'
    else:
        payments = Payment.query.order_by(Payment.date_created).all()
        wrappedPayments = []
        for payment in payments:
            balanceTemp = web3Interact.getBalanceOfAddress(
                payment.contract_address)
            wrappedPayment = {}
            wrappedPayment['payment'] = payment
            wrappedPayment['balance'] = balanceTemp
            wrappedPayments.append(wrappedPayment)

        db.session.close()
        return render_template('payment.html', wrappedPayments=wrappedPayments)


@app.route('/payment/create', methods=['GET'])
def newPaymentForm():
    return render_template('create_payment.html')


@app.route('/payment/release', methods=['GET'])
def releasePayment():
    paymentContractAddress = request.args.get('contractAddress')
    releaseAddress = request.args.get('releaseAddress')
    receipt = web3Interact.releasePayment(
        paymentContractAddress, releaseAddress)
    if receipt is not None:
        return jsonify({"status": "ok", "data": receipt})
    else:
        return jsonify({
            "status": "failed",
            "data": None
        })


@app.route('/collection', methods=['GET'])
def displayAdminOwnedNFTs():
    nfts = web3Interact.getOwnedNFTs(config.contractOwnerAddress)

    return render_template('collection.html', nfts=nfts)


@app.route('/nft/<string:tokenType>/<int:tokenId>', methods=['GET'])
def displayNFT(tokenType, tokenId):
    try:
        nft = web3Interact.getNFTByTokenId(tokenType, tokenId)
        tokenBalance = 1
        if tokenType == 'ERC1155':
            tokenBalance = web3Interact.getERC115TokenBalance(tokenId)
        
        try:
            db.session.execute("SELECT 1;")
            db.session.commit()
        except:
            db.session.rollback()
        finally:
            db.session.close()

        payments = Payment.query.order_by(Payment.date_created).all()
        args = request.args
        isListed = args.get("listingId") is not None
        listing = None
        if isListed is True:
            listing = web3Interact.getListingById(args.get("listingId"))

        print('contract address'+ nft.address)
        return render_template('nft.html', nft=nft, payments=payments, isListed=isListed, listing=listing, tokenBalance=tokenBalance)
    except Exception as e:
        result = {"status": "failed", "data": str(e)}
        return result, 500
    finally:
        db.session.close()


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/mint', methods=['GET', 'POST'])
def upload_file():
    print('in mint')
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            print('not file part')
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            print('no selected file')
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            pinresult = pinata_upload_file(os.path.join(
                app.config['UPLOAD_FOLDER'], filename), filename)
            pinresultJson = json.loads(pinresult)
            imageUrl = 'https://ipfs.digi96.com/ipfs/' + \
                pinresultJson['IpfsHash']
            payload = json.dumps({
                "name": request.form['name'],
                "image": imageUrl,
                "description": request.form['description'],
                "traits": [{"trait_type": "年代", "value": request.form['age']}, {"trait_type": "媒材", "value": request.form['media']},
                           {"trait_type": "尺寸", "value": request.form['size']}, {
                    "trait_type": "款識", "value": request.form['comment']},
                    {"trait_type": "鈐印", "value": request.form['stamp']}]
            })
            pinMetadatResult = pinata_upload_json(payload)
            print(pinMetadatResult)
            pinMetadatResultJson = json.loads(pinMetadatResult)
            print(pinMetadatResultJson['IpfsHash'])
            tokenUri = 'https://ipfs.digi96.com/ipfs/' + \
                pinMetadatResultJson['IpfsHash']
            #mintResult = web3Interact.mintNFT(tokenUri)
            # if mintResult['status'] == True:
            #   return redirect(url_for('displayAdminOwnedNFTs'))
            # else:
            #   return 'Failed to mint', 500
            txHash = web3Interact.mintNFT(int(request.form['amount']),tokenUri)
            print(txHash)
            return redirect(url_for('getTransactionStatus', txHash=txHash))

    return render_template('mint.html')


def pinata_upload_file(filepath, fileName):
    print(config.pinataJWT)
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"

    payload = {'pinataOptions': '{"cidVersion": 1}',
               'pinataMetadata': '{"name": "'+fileName+'", "keyvalues": {"company": "Emperor"}}'}
    files = [('file', ('cat.JPG', open(filepath, 'rb'), 'application/octet-stream'))]
    headers = {
        'Authorization': 'Bearer '+config.pinataJWT
    }
    response = requests.request(
        "POST", url, headers=headers, data=payload, files=files)
    print(response.text)
    # {"IpfsHash":"bafkreib3dq4th5n2acmclx34lhcdfrb4avr3m5rlcd6duolotg4vkelqha","PinSize":137929,"Timestamp":"2022-06-11T07:09:48.404Z"}
    return response.text


def pinata_upload_json(jsonPayload):
    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"

    headers = {'Content-Type': 'application/json',
               'Authorization': 'Bearer '+config.pinataJWT
               }

    response = requests.request("POST", url, headers=headers, data=jsonPayload)

    print(response.text)

    return response.text


@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)


@app.route('/transaction/<txHash>/status')
def getTransactionStatus(txHash):
    receipt = web3Interact.getTransactionReceipt(txHash)
    status = 'Incomplete'

    if receipt is None:
        return render_template('transaction_check.html', txHash=txHash, status=status)

    if receipt.status == 1:
        status = 'Success'
    else:
        status = 'Failed'
    return render_template('transaction_check.html', txHash=txHash, status=status)


@app.route('/admin/wallet')
def getAdminWallet():
    return render_template('admin_wallet.html', ownerAddress=config.contractOwnerAddress)


if __name__ == "__main__":
    app.run(debug=True)
