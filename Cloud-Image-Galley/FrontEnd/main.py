import base64
import os
from flask import render_template, request, g, redirect, url_for, jsonify
import requests
from FrontEnd import webapp
from utils.config import connect_to_database, ConfigAWS
import boto3
from botocore.errorfactory import ClientError
import json
from utils.Helpers import MD5Hasher

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.gif', '.tif', '.bmp', '.raw', '.cr2', '.nef', '.orf', '.sr2',
                      '.psd', '.xcf', '.ai', 'cdr'}
global bucket
bucket_name = 'group-31-images'
s3 = boto3.resource('s3',
                    region_name='us-east-1',
                    aws_access_key_id=ConfigAWS["aws_access_key_id"],
                    aws_secret_access_key=ConfigAWS['aws_secret_access_key'])
global memcacheIP_List
memcacheIP_List = []


def checkKeyBucket(file):
    """return true if exists in the bucket"""
    try:
        s3.meta.client.head_object(Bucket=bucket_name, Key=file)
    except ClientError:
        return False
    return True


def processDuplicateFilename(filename):
    """if duplicate file name found, add number after"""
    finalName = filename
    count = 1
    if checkKeyBucket(finalName):
        name, extension = os.path.splitext(finalName)
        finalName = name + str(count) + extension
    while checkKeyBucket(finalName):
        count = count + 1
        name, extension = os.path.splitext(finalName)
        finalName = name[:-1] + str(count) + extension
    return finalName


@webapp.route('/clearImageData', methods=['GET', 'POST'])
def clearImageData():
    try:
        # clear s3 data
        bucket.objects.all().delete()
        # clear RDS data
        cnx = get_db()
        cursor = cnx.cursor()
        # truncate image data from database
        query = '''TRUNCATE images;'''
        cursor.execute(query)
        data = {
            "success": "true",
        }
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json')
        cnx.commit()
    except:
        data = {
            "success": "false",
            "error": {
                "code": 500,
                "message": "Clear Data Error"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=500,
            mimetype='application/json')
    finally:
        if cnx:
            cnx.close()
    return response


@webapp.before_first_request
def runOnAppStart():
    global bucket
    requests.get('http://localhost:5000/manager/wakeUp')
    # either create a new bucket or return existing bucket if already exists
    bucket = s3.create_bucket(Bucket=bucket_name)
    # clean images in the s3 bucket upon application start
    bucket.objects.all().delete()
    # clear database data
    cnx = get_db()
    cursor = cnx.cursor()
    # truncate statistics data from database
    query = '''TRUNCATE statistics;'''
    cursor.execute(query)
    cnx.commit()
    cnx.close()
    clearImageData()
    res = requests.get("http://localhost:5000/scaler/getAllIPs")
    global memcacheIP_List
    memcacheIP_List = res.json()['ip_list']


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect_to_database()
    return db


def allowed_file(filename):
    """check if the file type is allowed"""
    return '.' in filename and ('.' + filename.rsplit('.', 1)[1]) in ALLOWED_EXTENSIONS


@webapp.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@webapp.route('/')
@webapp.route('/home')
def home():
    """Render Homepage, returns: home page html"""
    return render_template("home.html")


@webapp.route('/success')
def success():
    """Render success page"""
    msg = request.args.get('msg')
    return render_template("success.html", msg=msg)


@webapp.route('/failure')
def failure():
    """Render error page"""
    msg = request.args.get('msg')
    return render_template("failure.html", msg=msg)


@webapp.route('/listKeys', methods=['GET', 'POST'])
def listKeys():
    """Display the html page that shows all the keys in the database"""
    cnx = get_db()
    cursor = cnx.cursor()
    # get all image data from database
    query = '''SELECT image_key, image_path
                    FROM images;
                '''
    cursor.execute(query)
    rows = cursor.fetchall()
    cnx.close()
    return render_template("key_list.html", cursor=rows)


@webapp.route('/retrieve_key_form')
def retrieve_key_form():
    """Display an empty HTML form that allows users to browse image by key"""
    return render_template("key_form.html")


@webapp.route('/key', methods=['POST'])
def key():
    """Display the image user browsed by key"""
    if request.method == 'POST':
        image_key = request.form['key']
    else:
        return redirect(url_for('failure', msg="Method not allowed"))

    if not image_key:
        return redirect(url_for('failure', msg="Key is not given"))

    if image_key == '':
        return redirect(url_for('failure', msg="Key is empty"))
    IPAddressMemcache, ListBackUp = MD5Hasher(image_key, memcacheIP_List)
    dataSend = {"key": image_key}
    api_url = 'http://' + IPAddressMemcache + ':5001/GET'
    res = requests.post(api_url, json=dataSend)
    if res.status_code == 200:
        print("get image ----- hit")
        return render_template('show_image.html', key=image_key, image=res.json()['content'])
    else:
        print("not get image ----- miss")
        # if not in cache, get from database and call put in memcache
        cnx = get_db()
        cursor = cnx.cursor()

        # check if database has the key or not
        has_key = "SELECT image_path FROM images WHERE image_key = %s"

        cursor.execute(has_key, (image_key,))
        rows = cursor.fetchall()
        cnx.close()

        # database has the key, store the image key and the encoded image content pair in cache for next retrieval
        if len(rows) > 0:
            path = rows[0][0]
            try:
                obj = bucket.Object(path)
            except ClientError as e:
                if e.response['Error']['Code'] == "404":
                    return redirect(url_for('failure', msg="Key not exist in S3 error"))
            base64_image = base64.b64encode(obj.get()['Body'].read()).decode('utf-8')
            dataSend = {"key": image_key, "image": base64_image}
            IPAddressMemcache, ListBackUp = MD5Hasher(image_key, memcacheIP_List)
            api_url = 'http://' + IPAddressMemcache + ':5001/PUT'
            res = requests.post(api_url, json=dataSend)
            if res.status_code == 200:
                return render_template('show_image.html', key=image_key, image=base64_image)
            else:
                return redirect(url_for('failure', msg=res.json()['error']['message']))
        else:
            return redirect(url_for('failure', msg="Unknown Key"))


@webapp.route('/IPListUpdate')
def updateIPs():
    """Called from the managerApp to update memcacheIP_List.
    """
    ip_list = request.json["ip_list"]
    global memcacheIP_List
    memcacheIP_List = ip_list
    print("MemcacheIPList:", memcacheIP_List)
    return jsonify({"success": "true",
                    "statusCode": 200})


@webapp.route('/upload_form')
def upload_form():
    """Display an empty HTML form that allows users to define upload new key image pair"""
    return render_template("upload_form.html")


@webapp.route('/upload', methods=['POST'])
def upload():
    """
    Upload the key image pair. Store the image in s3 bucket and put the file location in the database
    calls invalidatekey in memcache.
    Returns: response object fot test
    """
    if request.method == 'POST':
        image_key = request.form['key']
        image_file = request.files['file']
    else:
        return redirect(url_for('failure', msg="Method not allowed"))

    if not image_file or not image_key:
        return redirect(url_for('failure', msg="Missing image file or key"))

    # check if file is empty
    if image_file.filename == '' or image_key == '':
        return redirect(url_for('failure', msg="Image file or key is empty"))

    # check if the uploaded file type is allowed
    if not allowed_file(image_file.filename):
        return redirect(url_for('failure', msg="Image file type not supported"))

    cnx = get_db()
    cursor = cnx.cursor()

    # check if database has the key or not
    has_key = ''' SELECT image_path FROM images WHERE image_key = %s'''
    cursor.execute(has_key, (image_key,))

    rows = cursor.fetchall()
    # handle duplicate filename
    filename = processDuplicateFilename(image_file.filename)
    # if the database has the key, delete the associated image in the s3 bucket
    # save new image in s3 bucket
    # and replace the old file name in the database with the new one
    if rows:
        file_to_delete = rows[0][0]
        s3.Object(bucket_name, file_to_delete).delete()
        try:
            s3.meta.client.upload_fileobj(image_file, bucket_name, filename)
        except ClientError as e:
            return redirect(url_for('failure', msg="Upload error"))
        query = '''UPDATE images SET image_path = %s WHERE image_key = %s'''
        cursor.execute(query, (filename, image_key))
        cnx.commit()
    # if database doesn't have the key, insert key, image pair into it.
    # save new image in s3 bucket
    else:
        try:
            s3.meta.client.upload_fileobj(image_file, bucket_name, filename)
        except ClientError as e:
            return redirect(url_for('failure', msg="Upload error"))
        query = ''' INSERT INTO images (image_key, image_path) VALUES (%s,%s)'''
        cursor.execute(query, (image_key, filename))
        cnx.commit()
    cnx.close()
    # invalidate key in memcache
    memIP, _ = MD5Hasher(image_key, memcacheIP_List)

    dataSend = {"key": image_key}
    res = requests.post('http://' + memIP + ':5001/invalidateKey', json=dataSend)
    if res.status_code != 200:
        return redirect(url_for('failure', msg="Invalidate key error"))
    else:
        return redirect(url_for('success', msg="Image Successfully Uploaded"))



"""FOR API TEST"""

@webapp.route('/api/list_keys', methods=['POST'])
def list_keys():
    """Return list_keys response"""
    if request.method == 'GET':
        data = {
            "success": "false",
            "error": {
                "code": 405,
                "message": "Method not allowed"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=405,
            mimetype='application/json')
        return response

    try:
        cnx = get_db()
        cursor = cnx.cursor()
        query = ''' SELECT image_key, image_path
                        FROM images;
                    '''
        cursor.execute(query)
        rows = cursor.fetchall()
        data = {
            "success": "true",
            "keys": [i[0] for i in rows]
        }
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json')
        cnx.close()
        return response
    except:
        data = {
            "success": "false",
            "error": {
                "code": 500,
                "message": "Internal error, unable to get the keys"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=500,
            mimetype='application/json')
        return response


@webapp.route('/api/upload', methods=['POST'])
def apiUpload():
    """
    Upload the key image pair. Store the image in local filesystem and put the file location in the database
    calls invalidatekey in memcache
    Returns: response object fot test
    """
    if request.method == 'GET':
        data = {
            "success": "false",
            "error": {
                "code": 405,
                "message": "Method not allowed"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=405,
            mimetype='application/json')
        return response

    image_key = request.form['key']
    image_file = request.files['file']

    if not image_file or not image_key:
        data = {
            "success": "false",
            "error": {
                "code": 401,
                "message": "Missing parameters"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=401,
            mimetype='application/json')
        return response

    # check if file is empty
    if image_file.filename == '' or image_key == '':
        data = {
            "success": "false",
            "error": {
                "code": 400,
                "message": "image file or key given is empty"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=400,
            mimetype='application/json')
        return response

    # check if the uploaded file type is allowed
    if not allowed_file(image_file.filename):
        data = {
            "success": "false",
            "error": {
                "code": 400,
                "message": "File type is not supported"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=400,
            mimetype='application/json')
        return response

    cnx = get_db()
    cursor = cnx.cursor()

    # check if database has the key or not
    has_key = ''' SELECT image_path FROM images WHERE image_key = %s'''
    cursor.execute(has_key, (image_key,))

    rows = cursor.fetchall()

    filename = processDuplicateFilename(image_file.filename)
    # if the database has the key, delete the associated image in the s3 bucket
    # save new image in s3 bucket
    # and replace the old file name in the database with the new one
    if rows:
        file_to_delete = rows[0][0]
        s3.Object(bucket_name, file_to_delete).delete()
        try:
            s3.meta.client.upload_fileobj(image_file, bucket_name, filename)
        except ClientError as e:
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "Upload file error"
                }}
            response = webapp.response_class(
                response=json.dumps(data),
                status=500,
                mimetype='application/json')
            return response
        query = '''UPDATE images SET image_path = %s WHERE image_key = %s'''
        cursor.execute(query, (filename, image_key))
        cnx.commit()
    # if database doesn't have the key, insert key, image pair into it.
    # save new image in s3 bucket
    else:
        try:
            s3.meta.client.upload_fileobj(image_file, bucket_name, filename)
        except ClientError as e:
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "Upload file error"
                }}
            response = webapp.response_class(
                response=json.dumps(data),
                status=500,
                mimetype='application/json')
            return response
        query = ''' INSERT INTO images (image_key, image_path) VALUES (%s,%s)'''
        cursor.execute(query, (image_key, filename))
        cnx.commit()
    cnx.close()
    # invalidate key in memcache
    memIP, _ = MD5Hasher(image_key, memcacheIP_List)
    dataSend = {"key": image_key}
    res = requests.post('http://' + memIP + ':5001/invalidateKey', json=dataSend)
    if res.status_code != 200:
        data = {
            "success": "false",
            "error": {
                "code": 500,
                "message": "Invalidate key error"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=500,
            mimetype='application/json')
        return response
    else:
        data = {
            "success": "true"
        }
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json')

        return response


@webapp.route('/api/key/<string:key_value>', methods=['POST'])
def apikey(key_value):
    if request.method == 'GET':
        data = {
            "success": "false",
            "error": {
                "code": 405,
                "message": "Method not allowed"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=405,
            mimetype='application/json')
        return response

    image_key = key_value
    if image_key == '':
        data = {
            "success": "false",
            "error": {
                "code": 400,
                "message": "Image Key is empty"
            }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=400,
            mimetype='application/json')
        return response

    # # find if this key image pair is in memcache, if so, retrieve and render it directly from cache.
    IPAddressMemcache, ListBackUp = MD5Hasher(image_key, memcacheIP_List)
    dataSend = {"key": image_key}
    api_url = 'http://' + IPAddressMemcache + ':5001/GET'
    res = requests.post(api_url, json=dataSend)

    if res.status_code == 200:
        image = res.json()['content']
        data = {
            "success": "true",
            "content": image
        }
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json'
        )
        return response
    else:
        # if not in cache, get from database and call put in memcache
        cnx = get_db()
        cursor = cnx.cursor()

        # check if database has the key or not
        has_key = ''' SELECT image_path FROM images WHERE image_key = %s'''

        cursor.execute(has_key, (image_key,))
        rows = cursor.fetchall()
        cnx.close()

        # database has the key, store the image key and the encoded image content pair in cache for next retrieval
        if rows:
            path = rows[0][0]
            try:
                obj = bucket.Object(path)
            except ClientError as e:
                if e.response['Error']['Code'] == "404":
                    data = {
                        "success": "false",
                        "error": {
                            "code": 500,
                            "message": "Key not exist in S3 error"
                        }}
                    response = webapp.response_class(
                        response=json.dumps(data),
                        status=500,
                        mimetype='application/json')
                    return response
            base64_image = base64.b64encode(obj.get()['Body'].read()).decode('utf-8')
            dataSend = {"key": image_key, "image": base64_image}
            IPAddressMemcache, ListBackUp = MD5Hasher(image_key, memcacheIP_List)
            api_url = 'http://' + IPAddressMemcache + ':5001/PUT'
            res = requests.post(api_url, json=dataSend)
            if res.status_code != 200:
                data = {
                    "success": "false",
                    "error": {
                        "code": 500,
                        "message": "Internal Error, memcache put error"
                    }}
                response = webapp.response_class(
                    response=json.dumps(data),
                    status=500,
                    mimetype='application/json'
                )
            else:
                data = {
                    "success": "true",
                    "content": base64_image
                }
                response = webapp.response_class(
                    response=json.dumps(data),
                    status=200,
                    mimetype='application/json'
                )
        else:
            data = {
                "success": "false",
                "error": {
                    "code": 404,
                    "message": "Unknown key"
                }}
            response = webapp.response_class(
                response=json.dumps(data),
                status=404,
                mimetype='application/json'
            )

        return response

