from os import environ
import requests
from flask import Flask, request
import logging
import json
import random

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
cities = {'москва': ['937455/1a2228b35a25d55a9304', '965417/44d7a4d16caf0f5b5276'],
          'нью-йорк': ['1540737/4b93d9c4aac421eb2b94', '1540737/a0acd2f7eb19927daf0e'],
          'париж': ["965417/27990f7ba9dca9a5a2ff", '965417/0f25cc57c5afe516db74']}
sessionStorage = {}


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)
    response = {'session': request.json['session'], 'version': request.json['version'],
                'response': {'end_session': False}}
    handle_dialog(response, request.json)
    logging.info('Response: %r', response)
    response["response"]["buttons"] = response["response"].get("buttons", []) + [{"title": "Помощь"}]
    return json.dumps(response)


def handle_dialog(res, req):
    if req["request"]["command"] == "помощь":
        res["response"]["text"] = "Я тебе буду показывать изображения городов, а ты будешь пытаться их отгадать."
        return
    user_id = req['session']['user_id']
    if req['session']['new']:
        res['response']['text'] = 'Привет! Назови своё имя!'
        sessionStorage[user_id] = {'first_name': None, 'game_started': False}
        return
    if sessionStorage[user_id]['first_name'] is None:
        first_name = get_first_name(req)
        if first_name is None:
            res['response']['text'] = 'Не расслышала имя. Повтори, пожалуйста!'
        else:
            sessionStorage[user_id]['first_name'] = first_name
            sessionStorage[user_id]['guessed_cities'] = []
            res['response']['text'] = f'Приятно познакомиться, {first_name.title()}. Я Алиса. Отгадаешь город по фото?'
            res['response']['buttons'] = [{'title': 'Да', 'hide': True}, {'title': 'Нет', 'hide': True}]
    else:
        if not sessionStorage[user_id]['game_started']:
            if 'да' in req['request']['nlu']['tokens']:
                if len(sessionStorage[user_id]['guessed_cities']) == 3:
                    res['response']['text'] = 'Ты отгадал все города!'
                    res['end_session'] = True
                else:
                    sessionStorage[user_id]['game_started'] = True
                    sessionStorage[user_id]['attempt'] = 1
                    play_game(res, req)
            elif 'нет' in req['request']['nlu']['tokens']:
                res['response']['text'] = 'Ну и ладно!'
                res['end_session'] = True
            elif 'Покажи город на карте' == req["request"]["original_utterance"]:
                res['response']['text'] = 'Посмотрел город на карте? Молодец! А теперь выбери, продолжать ли игру.'
                res['response']['buttons'] = [{'title': 'Да', 'hide': True}, {'title': 'Нет', 'hide': True}]
            else:
                res['response']['text'] = 'Не поняла ответа! Так да или нет?'
                res['response']['buttons'] = [{'title': 'Да', 'hide': True}, {'title': 'Нет', 'hide': True}]
        else:
            play_game(res, req)


def play_game(res, req):
    user_id = req['session']['user_id']
    attempt = sessionStorage[user_id]['attempt']
    if attempt == 1:
        city = random.choice(list(cities))
        while city in sessionStorage[user_id]['guessed_cities']:
            city = random.choice(list(cities))
        sessionStorage[user_id]['city'] = city
        res['response']['card'] = {}
        res['response']['card']['type'] = 'BigImage'
        res['response']['card']['title'] = 'Что это за город?'
        res['response']['card']['image_id'] = cities[city][attempt - 1]
        res['response']['text'] = 'Тогда сыграем!'
        sessionStorage[user_id]["country"] = 0
    else:
        country = sessionStorage[user_id]["country"]
        city = sessionStorage[user_id]['city']
        if country:
            if country.lower() == get_country(req):
                res['response']['text'] = 'Правильно! Сыграем ещё?'
                sessionStorage[user_id]['game_started'] = False
                res["response"]["buttons"] = [{"title": "Покажи город на карте", "hide": True,
                                               "url": f"https://yandex.ru/maps/?mode=search&text={city}"}]
            else:
                res['response']['text'] = f'Вы пытались. Это {country.title()}. Сыграем ещё?'
                sessionStorage[user_id]['game_started'] = False
        elif get_city(req) == city:
            res['response']['text'] = 'Правильно! А в какой стране этот город?'
            sessionStorage[user_id]['country'] = get_geo_info(city, "country")
            sessionStorage[user_id]['guessed_cities'].append(city)
        else:
            if attempt == 3:
                res['response']['text'] = f'Вы пытались. Это {city.title()}. Сыграем ещё?'
                sessionStorage[user_id]['game_started'] = False
                sessionStorage[user_id]['guessed_cities'].append(city)
                return
            else:
                res['response']['card'] = {}
                res['response']['card']['type'] = 'BigImage'
                res['response']['card']['title'] = 'Неправильно. Вот тебе дополнительное фото'
                res['response']['card']['image_id'] = cities[city][attempt - 1]
                res['response']['text'] = 'А вот и не угадал!'
    sessionStorage[user_id]['attempt'] += 1


def get_city(req):
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.GEO':
            return entity['value'].get('city', None)


def get_first_name(req):
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.FIO':
            return entity['value'].get('first_name', None)


def get_country(req):
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.GEO':
            return entity['value'].get('country', None)


def get_geo_info(city_name, type_info):
    info = requests.get(f"https://geocode-maps.yandex.ru/1.x/?geocode={city_name}&format=json&apikey=40d1649f-0493-4b70"
                        f"-98ba-98533de7710b").json()['response']['GeoObjectCollection']['featureMember'][0][
        'GeoObject']
    if type_info == 'country':
        return info['metaDataProperty']['GeocoderMetaData']['AddressDetails']['Country']['CountryName']
    elif type_info == 'coordinates':
        return [float(x) for x in info["Point"]["pos"].split()]


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(environ.get("PORT", 5000)))
