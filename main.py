import os
import telebot
import psycopg2
from datetime import datetime
from urllib.parse import urlparse
import socket

states = dict()
token = os.getenv('TOKEN')
soc_port = int(os.getenv('PORT'))

DATABASE_URL = os.getenv('DATABASE_URL')
result = urlparse(DATABASE_URL)
username = result.username
password = result.password
database = result.path[1:]
hostname = result.hostname
port = result.port

conn = None
try:
    conn = psycopg2.connect(
        database=database,
        user=username,
        password=password,
        host=hostname,
        port=port)

except (Exception, psycopg2.DatabaseError) as error:
    print(error)


def get_default_reply(message):
    return 'Неизвестная команда, пошлите /start для начала работы'


def start_session(message):
    states[message.chat.id] = 'started'
    return 'Бот готов принимать команды: \n' \
           '/add – добавление нового места;\n' \
           '/list – отображение добавленных мест;\n' \
           '/reset - позволяет пользователю удалить все его добавленные локации (помним про GDPR)'


def add_poi(message):
    poi_label = message.text
    poi_label = poi_label.replace('/add', '')
    poi_label = poi_label.strip()
    reply = 'Ошибка. Укажите название и адрес места после команды /add'
    if len(poi_label) > 0:
        now = datetime.now()
        sql = """INSERT INTO public.poi(chat_id, created, label)
                VALUES (%s, %s, %s);"""
        cur = conn.cursor()
        cur.execute(sql, (message.chat.id, now, poi_label))
        conn.commit()
        reply = 'Добавлено'
    return reply


def list_poi(message):
    chat_id = message.chat.id
    sql = 'SELECT id, chat_id, created, label, latitude, longitude, image' \
          ' FROM public.poi' \
          ' WHERE chat_id={}' \
          ' ORDER BY created DESC' \
          ' LIMIT 10;'.format(chat_id)

    cur = conn.cursor()
    cur.execute(sql)
    reply = 'Найдено мест: {}'.format(cur.rowcount) + '\n'
    row = cur.fetchone()

    while row is not None:
        created = row[2].strftime('%Y-%m-%d %H:%M:%S')
        reply = reply + '* ' + row[3] + ', добавлено: ' + created + '\n'
        row = cur.fetchone()

    return reply


def reset_session(message):
    chat_id = message.chat.id
    sql = 'DELETE FROM public.poi WHERE chat_id={};'.format(chat_id)
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    reply = 'Удалено мест: {}'.format(cur.rowcount) + '\n'
    return reply


commands = {'/add': add_poi,
            '/list': list_poi,
            '/reset': reset_session}

bot = telebot.TeleBot(token)


@bot.message_handler()
def handle_message(message):
    print(message.text)
    # если это первое сообщение, регистрируем его в каталоге
    try:
        _ = states[message.chat.id]
    except KeyError:
        states[message.chat.id] = None

    if message.text.find('/start') != -1:
        reply = start_session(message)
    else:
        reply = get_default_reply(message)

    if states[message.chat.id] is not None:
        for com, func in commands.items():
            if message.text.find(com) != -1:
                reply = func(message)

    bot.send_message(chat_id=message.chat.id, text=reply)


sock = socket.socket()
sock.bind(('', soc_port))
sock.listen(1)

bot.polling()


