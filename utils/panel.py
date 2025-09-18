from telebot import types
def owner_panel_markup():
    m=types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton('📋 Groups',callback_data='list_groups'))
    m.add(types.InlineKeyboardButton('📝 New Schedule',callback_data='new_schedule'))
    m.add(types.InlineKeyboardButton('🚀 Instant Broadcast',callback_data='instant_broadcast'))
    m.add(types.InlineKeyboardButton('❌ Cancel All',callback_data='cancel_schedules'))
    return m
