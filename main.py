from telegram.ext import *
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Update

import langid
import translators as ts
from repository.sqlite_repository import SQLiteRepository

with open('token.txt', 'r') as file:
    tn = file.read().replace('\n', '')


class Language:
    def __init__(self, full_name: str, lang_id: int, glang_shorty: str):
        self.full_name = full_name
        self.id = lang_id
        self.glang_shorty = glang_shorty


languages = dict()
language_buttons = []


def init_languages():
    languages[0] = Language("Английский", 0, 'en')
    languages[1] = Language("Испанский", 1, 'es')
    languages[2] = Language("Немецкий", 2, 'de')

    for lang in languages.values():
        language_buttons.append([InlineKeyboardButton(lang.full_name, callback_data="lang: " + str(lang.id))])


class Command:
    def __init__(self, name: str, action, desc: str):
        self.name = name
        self.action = action
        self.desc = desc


def init_command_reply_board(coms: list[Command]):
    reply_board_names = []
    for com in coms:
        reply_board_names.append(["/" + com.name])
    return ReplyKeyboardMarkup(reply_board_names, one_time_keyboard=False)


class Translator:
    def __init__(self, current_lang: Language):
        self.lang = current_lang

    def switch_language(self, language: Language):
        self.lang = language

    def do_translate(self, text: str):
        text_lang = langid.classify(text)
        if text_lang[0] == self.lang.glang_shorty:
            return ts.translate_text(text, from_language=self.lang.glang_shorty, to_language='ru')
        else:
            return ts.translate_text(text, to_language=self.lang.glang_shorty)


class UserTableEntry:
    def __init__(self, user_id, target_lang, word):
        self.user_id = user_id
        self.target_lang = target_lang
        self.word = word


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot entry command"""
    await update.message.reply_text('Добро пожаловать в PolyGlotBot!\n Список доступных команд:', reply_markup=
                                    main_state.reply_keyboard)
    await main_state.execute_command('help', update, context)
    context.chat_data['state'] = main_state
    context.chat_data['lang'] = Translator(languages[0])
    return MAIN_STATE


async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Language switch option."""
    await update.message.reply_text("Выбери язык:", reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline keyboard handler."""
    query = update.callback_query
    variant = query.data

    await query.answer()

    if variant.startswith('lang: '):
        lang = languages[int(variant[len('lang: '):])]
        await query.edit_message_text(text=f"Выбранный язык: {lang.full_name}")
        context.chat_data['lang'].switch_language(lang)


async def text_for_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Translate given phrase."""
    words = update.message.text.split()
    for word in words:
        word_book.add(UserTableEntry(update.message.from_user['id'], context.chat_data['lang'].lang.glang_shorty, word))
    await update.message.reply_text(context.chat_data['lang'].do_translate(update.message.text))


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Show current options. """
    cur_lang = context.chat_data['lang'].lang.full_name
    await update.message.reply_text(f'Текущие настройки:\n Язык - ' + cur_lang + '\nРежим: ' +
                                    context.chat_data['state'].help_name)


async def show_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show words being prompted before."""
    cur_lang = context.chat_data['lang'].lang.glang_shorty
    user_id = update.message.from_user['id']
    words = word_book.get_all({'user_id': user_id, 'target_lang': cur_lang})
    words_list_str = ''
    for word in words:
        words_list_str += word.word + ' : ' + context.chat_data['lang'].do_translate(word.word) + '\n'
    display_message = 'Вами было изучено ' + str(len(words)) + 'слов:\n' + words_list_str

    await update.message.reply_text(display_message)


async def null_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Do nothing."""
    pass


async def common_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command dispatcher for BotState."""
    state = context.chat_data['state']
    command_name = update.message.text[1:]
    next_state = await state.execute_command(command_name, update, context)
    context.chat_data['state'] = next_state
    return next_state.id


class BotState:
    """
    Represents a state in ConversationHandler.

    It used to insert automatic transition between states
    and keeping reply keyboard filled with current state
    commands.

    """

    def __init__(self, state_id: int, help_name: str):
        self.id = state_id
        self.help_name = help_name
        self.custom_handlers = []
        self.command_list = {}
        self.reply_keyboard = None

    def add_command(self, command: Command, next_state, state_switch_message=''):
        """Add single command handler to state."""
        self.command_list[command.name] = [command, next_state, state_switch_message]

    def add_custom_handler(self, custom_handler):
        """Add any handler to state."""
        self.custom_handlers.append(custom_handler)

    async def execute_command(self, name: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Execute command and switch to next state. Called by common_command_handler()."""
        if name == 'help':
            await self.__show_help(update, context)
            return self

        if name in self.command_list:
            command = self.command_list[name]
            if command[1] is not self:
                await update.message.reply_text(command[2], reply_markup=command[1].reply_keyboard)
            await command[0].action(update, context)
            return command[1]
        else:
            return self

    async def __show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help for current state commands."""
        help_text = ''
        for command in self.command_list.values():
            help_text += '/' + command[0].name + " - " + command[0].desc + '\n'
        await update.message.reply_text(help_text)

    def build(self):
        """Builds a list of handlers used to create ConversationHandler. Also creates a reply keyboard."""
        just_command_list = []
        for com in self.command_list.values():
            just_command_list.append(com[0])
        self.reply_keyboard = init_command_reply_board(just_command_list)
        handlers = []
        for com in just_command_list:
            handlers.append(CommandHandler(com.name, common_command_handler))
        for custom_handler in self.custom_handlers:
            handlers.append(custom_handler)

        handlers.append(CommandHandler('help', common_command_handler))
        return handlers


MAIN_STATE, TRANSLATING = range(2)


def init_states():
    """Builds a list of states used by bot in conversation. Main state is first in list."""
    
    main_state = BotState(MAIN_STATE, 'ожидание команд')
    translating_state = BotState(TRANSLATING, 'переводчик')

    main_state.add_command(Command('translate', null_action, 'войти в режим переводчика'),
                                       translating_state, 'Введите текст для перевода')
    main_state.add_command(Command('choose_lang', choose_lang, 'выбрать другой язык'), main_state)
    main_state.add_command(Command('show_words', show_words, 'показать изученные слова'), main_state)
    main_state.add_command(Command('status', show_status, 'показать текущие настройки'), main_state)
    main_state.add_custom_handler(CallbackQueryHandler(button))

    translating_state.add_command(Command('done', null_action, 'stop translation'), main_state,
                                  'Выход из режима переводчика')
    translating_state.add_command(Command('status', show_status, 'показать текущие настройки'),
                                  translating_state)
    translating_state.add_custom_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_for_translate))

    states_list = [main_state, translating_state]

    return states_list


if __name__ == '__main__':
    # Init repository to store per-user prompted words
    word_book = SQLiteRepository(':memory:', 'word_book', {'user_id': 'INTEGER', 'target_lang': 'TEXT', 'word': 'TEXT'},
                                 UserTableEntry)

    # Init states for conversation
    states = init_states()
    main_state = states[0]
    states_dict = {}
    for state in states:
        states_dict[state.id] = state.build()

    # Init language table and translator
    init_languages()
    reply_markup = InlineKeyboardMarkup(language_buttons)
    translator = Translator(languages[0])

    application = Application.builder().token(tn).build()

    # Main conversation handler
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states=states_dict,
        fallbacks=[MessageHandler(filters.Regex("^Done$"), null_action)],
    ))

    # Run bot
    print('running....')
    application.run_polling(1.0)
