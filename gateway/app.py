import os
from flask import Flask, jsonify
from flask import abort
from flask import make_response
from flask import request
import requests
import datetime
import json
import uuid
from curses.ascii import NUL

port = os.environ.get('PORT')
if port is None:
    port = 8080

app = Flask(__name__)


@app.route('/api/v1/test', methods=['GET'])
def get_test():
    return make_response(jsonify({'test': 'ok', 'port': port}), 200)

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found in gateway'}), 404)

#получить список отелей
@app.route('/api/v1/hotels', methods=['GET'])
def get_hotels():
    authorization = request.headers.get('Authorization')
    if not authorization:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'No Authorization header'}), 401)
    authorization = authorization[7:]
    response_auth = requests.get('http://auth:8040/api/v1/check_token', params = {'token': authorization})
    if response_auth.status_code != 200:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'Not valid token', 'We have gotten': authorization}), 401)

    page = request.args.get('page', default=0, type= int)
    size = request.args.get('size', default=0, type= int)
    response = requests.get('http://reservation:8070/api/v1/hotels', params = {'page': page, 'size': size})
    return make_response(response.json(), 200)

#получить информацию о статусе в системе лояльности
@app.route('/api/v1/loyalty', methods=['GET'])
def get_loyalty():
    authorization = request.headers.get('Authorization')
    if not authorization:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'No Authorization header'}), 401)
    authorization = authorization[7:]
    response_auth = requests.get('http://auth:8040/api/v1/check_token', params = {'token': authorization})
    if response_auth.status_code != 200:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'Not valid token', 'We have gotten': authorization}), 401)
    username = response_auth.json()['user']

    response = requests.get('http://loyalty:8050/api/v1/loyalty', params = {'username': username})
    return make_response(response.json(), 200)

#забронировать отель
@app.route('/api/v1/reservations', methods=['POST'])
def create_person():
    authorization = request.headers.get('Authorization')
    if not authorization:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'No Authorization header'}), 401)
    authorization = authorization[7:]
    response_auth = requests.get('http://auth:8040/api/v1/check_token', params = {'token': authorization})
    if response_auth.status_code != 200:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'Not valid token', 'We have gotten': authorization}), 401)
    username = response_auth.json()['user']

    discount_computed = False
    find_hotel_id = False
    payment_complited = False
    response_loyalty_up = False
    hotel_uid = ''
    price = 0
    total_price = 0
    discount = 0
    reservationUid = ''
    status = ''
    if not request.json:
        abort(400)
    if 'hotelUid' not in request.json or 'startDate' not in request.json or 'endDate' not in request.json:
        abort(400)

    #получаем список отелей
    response_hotels = requests.get('http://reservation:8070/api/v1/hotels')
    result_hotels = response_hotels.json()
    #узнаем статус в системе лояльности
    response_loyalty = requests.get('http://loyalty:8050/api/v1/loyalty', params = {'username': username})
    if response_loyalty.status_code == 200:
        discount = response_loyalty.json()['discount']
        discount_computed = True
    elif response_loyalty.status_code == 404:
        discount = 0
        discount_computed = True
    else:
        return make_response(jsonify({"discount_computed": False}), 400)
    
    date_time_str_startDate = request.json['startDate']
    date_time_str_endDate = request.json['endDate']
    date_time_obj_startDate = datetime.datetime.strptime(date_time_str_startDate, '%Y-%m-%d')
    date_time_obj_endDate = datetime.datetime.strptime(date_time_str_endDate, '%Y-%m-%d')
    duration = date_time_obj_endDate - date_time_obj_startDate
    days = duration.days

    for i in range(len(result_hotels['items'])):
        if result_hotels['items'][i]['hotelUid'] == request.json['hotelUid']:
            find_hotel_id = True
            hotel_id = result_hotels['items'][i]['hotel_id']
            hotel_uid = result_hotels['items'][i]['hotelUid']
            price = result_hotels['items'][i]['price']
            break

    if find_hotel_id:
        if discount_computed:
            total_price = int((days * price) - (((days * price) / 100) * discount))
            #проводим платеж
            response_payment = requests.post('http://payment:8060/api/v1/post_payment', data = {'price': total_price})
            if response_payment.status_code == 201:
                paymentUid = response_payment.json()['payment_uid']
                status = response_payment.json()['status']
                #поднимаем статус в системе лояльности
                response_loyalty_up = requests.patch('http://loyalty:8050/api/v1/loyalty_up', data = {'username': username})
                if response_loyalty_up.status_code == 200:
                    #бронируем
                    reservationUid = str(uuid.uuid4())
                    reserv_dict = {
                    'reservationUid': reservationUid,
                    'username': username,
                    'paymentUid': paymentUid,
                    'hotel_id': hotel_id,
                    'status': status,
                    'startDate': date_time_obj_startDate,
                    'endDate': date_time_obj_endDate
                    }
                    response_reservate = requests.post('http://reservation:8070/api/v1/reservate', data = reserv_dict)
                    if response_reservate.status_code == 201:
                        return make_response(jsonify({
                            "reservationUid": reservationUid,
                            "hotelUid": hotel_uid, 
                            "startDate": date_time_str_startDate, 
                            "endDate": date_time_str_endDate,
                            "discount": discount, 
                            "status": status, 
                            "payment": { 
                                "status": status,
                                "price": total_price
                            }
                        }), 200)
                    else:
                        return make_response(jsonify({'reservate': False}), 400)
                else:
                    return make_response(jsonify({'loyalty_up_completed': False}), 400)
            else:
                return make_response(jsonify({'payment_completed': False}), 400)
    else:
        return make_response(jsonify({"find_hotel_uid": False}), 400)

#получить информацию по конкретному бронированию
@app.route('/api/v1/reservations/<reservationUid>', methods=['GET'])
def get_reservation(reservationUid):
    authorization = request.headers.get('Authorization')
    if not authorization:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'No Authorization header'}), 401)
    authorization = authorization[7:]
    response_auth = requests.get('http://auth:8040/api/v1/check_token', params = {'token': authorization})
    if response_auth.status_code != 200:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'Not valid token', 'We have gotten': authorization}), 401)
    username = response_auth.json()['user']

    response_reservations = requests.get('http://reservation:8070/api/v1/get_user_reservations', params = {'username': username})
    response_reservations = response_reservations.json()
    result = []
    tmp = []
    for i in response_reservations:
        if i['reservationUid'] == reservationUid:
            tmp.append(i)
            break
    if len(tmp) > 0:
        for r in tmp:
            paymentUid = r['paymentUid']
            response_payment = requests.get('http://payment:8060/api/v1/get_payment', params = {'paymentUid': paymentUid})
            result.append({
                    'reservationUid': r['reservationUid'], 
                    'payment': response_payment.json(),
                    'hotel': {
                            'hotelUid': r['hotel']['hotelUid'],
                            'name': r['hotel']['name'],
                            'fullAddress': r['hotel']['fullAddress'],
                            'stars': r['hotel']['stars'],
                            }, 
                    'status': r['status'],  
                    'startDate': r['startDate'], 
                    'endDate': r['endDate']})



        return make_response(result[0], 200)
    else:
        return make_response(jsonify({}), 400)

#удаление бронирования
@app.route('/api/v1/reservations/<reservationUid>', methods=['DELETE'])
def cancel_reservation(reservationUid):
    authorization = request.headers.get('Authorization')
    if not authorization:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'No Authorization header'}), 401)
    authorization = authorization[7:]
    response_auth = requests.get('http://auth:8040/api/v1/check_token', params = {'token': authorization})
    if response_auth.status_code != 200:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'Not valid token', 'We have gotten': authorization}), 401)
    username = response_auth.json()['user']

    response_reservation = requests.post('http://reservation:8070/api/v1/cancel_reservation', data = {'reservationUid': reservationUid})
    if response_reservation.status_code == 201:
        paymentUid = response_reservation.json()['paymentUid']
        response_payment = requests.post('http://payment:8060/api/v1/cancel_payment', data = {'paymentUid': paymentUid})
        if response_payment.status_code == 201:
            response_loyalty = requests.post('http://loyalty:8050/api/v1/loyalty_down', data = {'username': username})
            if response_loyalty.status_code == 201:
                return make_response(jsonify({}), 204)
            else:
                return make_response(jsonify({'loyalty': False}), 400)
        else:
            return make_response(jsonify({'payment': False}), 400)
    else:
        return make_response(jsonify({'reservation': False}), 400)

    

#инормация по всем бронированиям пользователя
@app.route('/api/v1/reservations', methods=['GET'])
def get_reservations():
    authorization = request.headers.get('Authorization')
    if not authorization:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'No Authorization header'}), 401)
    authorization = authorization[7:]
    response_auth = requests.get('http://auth:8040/api/v1/check_token', params = {'token': authorization})
    if response_auth.status_code != 200:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'Not valid token', 'We have gotten': authorization}), 401)
    username = response_auth.json()['user']

    response_reservation = requests.get('http://reservation:8070/api/v1/get_user_reservations', params = {'username': username})
    result = []
    for r in response_reservation.json():
        paymentUid = r['paymentUid']
        response_payment = requests.get('http://payment:8060/api/v1/get_payment', params = {'paymentUid': paymentUid})
        result.append({
                'reservationUid': r['reservationUid'], 
                'payment': response_payment.json(),
                'hotel': {
                        'hotelUid': r['hotel']['hotelUid'],
                        'name': r['hotel']['name'],
                        'fullAddress': r['hotel']['fullAddress'],
                        'stars': r['hotel']['stars'],
                        }, 
                'status': r['status'],  
                'startDate': r['startDate'], 
                'endDate': r['endDate']})


    return make_response(jsonify(result), 200)

#информация о всех бронированиях и статусе в сисеме лояльности пользователя
@app.route('/api/v1/me', methods=['GET'])
def me():
    authorization = request.headers.get('Authorization')
    if not authorization:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'No Authorization header'}), 401)
    authorization = authorization[7:]
    response_auth = requests.get('http://auth:8040/api/v1/check_token', params = {'token': authorization})
    if response_auth.status_code != 200:
        return make_response(jsonify({'error': 'access_denied', 'error_description': 'Not valid token', 'We have gotten': authorization}), 401)
    username = response_auth.json()['user']

    response_reservations = requests.get('http://reservation:8070/api/v1/get_user_reservations', params = {'username': username})
    result = []
    for r in response_reservations.json():
        paymentUid = r['paymentUid']
        response_payment = requests.get('http://payment:8060/api/v1/get_payment', params = {'paymentUid': paymentUid})
        result.append({
                'reservationUid': r['reservationUid'], 
                'payment': response_payment.json(),
                'hotel': {
                        'hotelUid': r['hotel']['hotelUid'],
                        'name': r['hotel']['name'],
                        'fullAddress': r['hotel']['fullAddress'],
                        'stars': r['hotel']['stars'],
                        }, 
                'status': r['status'],  
                'startDate': r['startDate'], 
                'endDate': r['endDate']})
    response_loyalty = requests.get('http://loyalty:8050/api/v1/loyalty', params = {'username': username})
    return make_response(jsonify({'reservations': result, 'loyalty': response_loyalty.json()}), 200)

#получить токен
@app.route('/oauth/token', methods=['POST'])
def get_token():
    if 'scope' not in request.form:
        abort(400)
    scope = request.form['scope']
    if 'grant_type' not in request.form:
        abort(400)
    grant_type = request.form['grant_type']
    if 'username' not in request.form:
        abort(400)
    username = request.form['username']
    if 'password' not in request.form:
        abort(400)
    password = request.form['password']
    if 'clientId' not in request.form:
        abort(400)
    clientId = request.form['clientId']
    if 'clientSecret' not in request.form:
        abort(400)
    clientSecret = request.form['clientSecret']

    response_auth = requests.get('http://auth:8040/api/v1/get_token', params = {'username': username, 'password': password, 'clientId': clientId, 'clientSecret': clientSecret})
    if response_auth.status_code == 200:
        return make_response(response_auth.json(), 200)
    else:
        return make_response(jsonify({"error": "access_denied", "error_description": "Unauthorized"}), 401)


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=int(port))
