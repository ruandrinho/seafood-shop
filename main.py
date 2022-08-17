import logging
import os
import requests
import moltin
from dotenv import load_dotenv
from textwrap import dedent
from contextlib import suppress
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    Updater,
    Filters,
)

logger = logging.getLogger(__name__)

START, HANDLE_MENU, HANDLE_PRODUCT, HANDLE_CART, AWAIT_EMAIL = range(5)


def start(update, context):
    # logger.info(context.bot_data['moltin_client_id'])
    keyboard = []
    for product in moltin.get_all_products():
        keyboard.append([InlineKeyboardButton(product['name'], callback_data=product['id'])])
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='cart')])
    update.message.reply_text(
        'Добро пожаловать в магазин. Выберите товар:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return HANDLE_MENU


def show_menu(update, context):
    query = update.callback_query
    query.answer()
    keyboard = []
    for product in moltin.get_all_products():
        keyboard.append([InlineKeyboardButton(product['name'], callback_data=product['id'])])
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='cart')])
    query.message.reply_text(
        'Выберите товар:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    query.message.delete()
    return HANDLE_MENU


def show_menu_after_product(update, context):
    query = update.callback_query
    query.answer()
    cart_product_id, cart_product_quantity = query.data.split('=')
    with suppress(requests.exceptions.HTTPError):
        moltin.add_product_to_cart(cart_product_id, int(cart_product_quantity), query.from_user.id)
    keyboard = []
    for product in moltin.get_all_products():
        keyboard.append([InlineKeyboardButton(product['name'], callback_data=product['id'])])
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='cart')])
    query.message.reply_text(
        'Выберите товар:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    query.message.delete()
    return HANDLE_MENU


def show_product(update, context):
    query = update.callback_query
    query.answer()
    product = moltin.get_product(query.data)
    keyboard = []
    if product['stock'] > 0:
        keyboard.append([(InlineKeyboardButton('1 кг', callback_data=f'{query.data}=1'))])
    if product['stock'] > 4:
        keyboard[0].append(InlineKeyboardButton('5 кг', callback_data=f'{query.data}=5'))
    if product['stock'] > 9:
        keyboard[0].append(InlineKeyboardButton('10 кг', callback_data=f'{query.data}=10'))
    keyboard.append([
        InlineKeyboardButton('Корзина', callback_data='cart'),
        InlineKeyboardButton('Назад', callback_data='back')
    ])
    message = f'''\
        {product["name"]}

        {product["price"]} per kg
        {product["stock"]}kg on stock

        {product["description"]}
        '''
    query.message.reply_photo(
        photo=product['image_url'],
        caption=dedent(message),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    query.message.delete()
    return HANDLE_PRODUCT


def show_cart(update, context):
    query = update.callback_query
    query.answer()
    if query.data != 'cart':
        moltin.remove_product_from_cart(query.data, query.from_user.id)
    cart_products, cart_cost, cart_summary = moltin.get_cart_data(query.from_user.id)
    keyboard = []
    keyboard.append([InlineKeyboardButton('Оплатить', callback_data='pay')])
    for product in cart_products:
        keyboard.append(
            [InlineKeyboardButton(f'Убрать из корзины {product["name"]}', callback_data=product['id'])]
        )
    keyboard.append([InlineKeyboardButton('В меню', callback_data='back')])
    if cart_summary:
        message = f'{cart_summary}Total: {cart_cost}'
    else:
        message = 'Товаров пока нет.'
    query.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    query.message.delete()
    return HANDLE_CART


def ask_for_email(update, context):
    query = update.callback_query
    query.answer()
    query.message.reply_text(
        'Пожалуйста, введите email для оформления покупки'
    )
    query.message.delete()
    return AWAIT_EMAIL


def finish(update, context):
    email = update.message.text
    update.message.reply_text(
        f'Вы прислали почту {email}. Скоро с вами свяжутся наши менеджеры!'
    )
    moltin.save_customer(email, update.message.from_user)
    return HANDLE_MENU


def main():
    load_dotenv()

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    updater = Updater(
        os.getenv('TELEGRAM_TOKEN'),
        persistence=PicklePersistence(filename='conversationbot')
    )
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            HANDLE_MENU: [
                CallbackQueryHandler(show_cart, pattern='^cart$'),
                CallbackQueryHandler(show_product)
            ],
            HANDLE_CART: [
                CallbackQueryHandler(ask_for_email, pattern='^pay$'),
                CallbackQueryHandler(show_menu, pattern='^back$'),
                CallbackQueryHandler(show_cart)
            ],
            HANDLE_PRODUCT: [
                CallbackQueryHandler(show_cart, pattern='^cart$'),
                CallbackQueryHandler(show_menu, pattern='^back$'),
                CallbackQueryHandler(show_menu_after_product)
            ],
            AWAIT_EMAIL: [
                MessageHandler(Filters.text & ~Filters.command, finish)
            ]
        },
        fallbacks=[],
        name='seafood_conversation',
        persistent=True
    )

    # application.bot_data['moltin_client_id'] = os.getenv('MOLTIN_CLIENT_ID')
    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
