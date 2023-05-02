from telegram.ext import *
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, constants, InlineKeyboardButton, User, Update

import random as rd
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
        language_buttons.append([InlineKeyboardButton(
            lang.full_name, callback_data="lang: " + str(lang.id))])


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
            return ts.translate_text(
                text,
                from_language=self.lang.glang_shorty,
                to_language='ru')
        else:
            return ts.translate_text(text, to_language=self.lang.glang_shorty)


class UserTableEntry:
    def __init__(self, user_id, target_lang, phrase):
        self.user_id = user_id
        self.target_lang = target_lang
        self.phrase = phrase


class QuizScoreTableEntry:
    def __init__(self, user_id, user_name: str, lang: str, score: int):
        self.user_id = user_id
        self.user_name = user_name
        self.lang = lang
        self.score = score


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot entry command"""
    await update.message.reply_text('Добро пожаловать в PolyGlotBot!\n Список доступных команд:', reply_markup=main_state.reply_keyboard)
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
        await query.edit_message_text(text=f"Выбранный язык: *{lang.full_name}*", parse_mode=constants.ParseMode.MARKDOWN_V2)
        context.chat_data['lang'].switch_language(lang)


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cur_lang = context.chat_data['lang'].lang.glang_shorty
    user_id = update.message.from_user['id']
    words = word_book.get_all({'user_id': user_id, 'target_lang': cur_lang})
    context.chat_data['quiz_score'] = 0
    context.chat_data['quiz_word_pool'] = words


async def quiz_next_quest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cur_lang = context.chat_data['lang'].lang.glang_shorty
    trans = context.chat_data['lang']
    user_id = update.message.from_user['id']

    pool = context.chat_data['quiz_word_pool']
    phrase_ids = rd.sample(range(len(pool)), k=4)
    correct_ans_idx = rd.randrange(4)
    phrase = pool[phrase_ids[correct_ans_idx]].phrase
    context.chat_data['quiz_correct_ans'] = str(correct_ans_idx)
    answers_buttons = []

    for i in range(4):
        answers_buttons.append([InlineKeyboardButton(trans.do_translate(
            pool[phrase_ids[i]].phrase), callback_data=str(i))])
    reply_quiz = InlineKeyboardMarkup(answers_buttons)
    await update.message.reply_text('Выберите правильный перевод фразы:\n *' + phrase + '*', reply_markup=reply_quiz, parse_mode=constants.ParseMode.MARKDOWN_V2)


def update_scoreboard(user: User, lang: str, score: int):
    user_id = user['id']
    entry = quiz_scoreboard.get_all({'user_id': user_id, 'lang': lang})
    if len(entry) != 0:
        if entry[0].score > score:
            return
        else:
            entry[0].score = score
            quiz_scoreboard.update(entry[0])
    else:
        quiz_scoreboard.add(
            QuizScoreTableEntry(
                user_id,
                user['username'],
                lang,
                score))


async def show_scoreboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur_lang = context.chat_data['lang'].lang
    top_n = quiz_scoreboard.get_first_ordered(
        'score', 10, True, {'lang': cur_lang.glang_shorty})
    text_board = ''
    i = 1
    for entry in top_n:
        text_board += f'#{i}: @{entry.user_name} : {entry.score}\n'
        i += 1
    await update.message.reply_text(f'Таблица рекордов для языка {cur_lang.full_name}:\n' + text_board)


async def quiz_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    cur_lang = context.chat_data['lang'].lang.glang_shorty
    score = context.chat_data['quiz_score']
    update_scoreboard(user, cur_lang, score)
    await update.message.reply_text(f'Ваш результат ({score}) был сохранен.\n')


async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline keyboard handler."""
    query = update.callback_query
    variant = query.data

    await query.answer()

    cur_lang = context.chat_data['lang'].lang.glang_shorty
    if variant == context.chat_data['quiz_correct_ans']:
        context.chat_data['quiz_score'] += 1
        score = context.chat_data['quiz_score']
        await query.edit_message_text(text=f"Ваш ответ правильный! Всего очков набрано: {score}(+1)")
        return QUIZ
    else:
        context.chat_data['quiz_score'] += 1
        score = context.chat_data['quiz_score']
        update_scoreboard(query.from_user, cur_lang, score)
        await query.edit_message_text(text=f"Ваш ответ неверный! Квиз окончен.\nВсего очков набрано: {score}")
        await query.message.reply_text("Выходим...\n", reply_markup=main_state.reply_keyboard)
        context.chat_data['state'] = main_state
        return MAIN_STATE


async def text_for_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Translate given phrase."""
    word_book.add(
        UserTableEntry(
            update.message.from_user['id'],
            context.chat_data['lang'].lang.glang_shorty,
            update.message.text))
    await update.message.reply_text(context.chat_data['lang'].do_translate(update.message.text))


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Show current options. """
    cur_lang = context.chat_data['lang'].lang.full_name
    await update.message.reply_text(f'Текущие настройки:\n Язык - *' + cur_lang + '*\nРежим: *' +
                                    context.chat_data['state'].help_name + '*', parse_mode=constants.ParseMode.MARKDOWN_V2)


async def show_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show words being prompted before."""
    cur_lang = context.chat_data['lang'].lang.glang_shorty
    user_id = update.message.from_user['id']
    words = word_book.get_all({'user_id': user_id, 'target_lang': cur_lang})
    words_list_str = ''
    for word in words:
        words_list_str += word.phrase + ' : ' + \
            context.chat_data['lang'].do_translate(word.phrase) + '\n'
    display_message = 'Вами было изучено ' + \
        str(len(words)) + ' слов и выражений:\n' + words_list_str

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

    def add_command(
            self,
            command: Command,
            next_state,
            state_switch_message=''):
        """Add single command handler to state."""
        self.command_list[command.name] = [
            command, next_state, state_switch_message]

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


MAIN_STATE, TRANSLATING, QUIZ = range(3)


def init_states():
    """Builds a list of states used by bot in conversation. Main state is first in list."""

    # Init empty states.
    main_state = BotState(MAIN_STATE, 'ожидание команд')
    translating_state = BotState(TRANSLATING, 'переводчик')
    quiz_state = BotState(QUIZ, 'квиз')

    # fill main state commands
    main_state.add_command(
        Command(
            'translate',
            null_action,
            'войти в режим переводчика'),
        translating_state,
        'Введите текст для перевода')
    main_state.add_command(
        Command(
            'quiz',
            start_quiz,
            'начать квиз по изученным словам'),
        quiz_state,
        'Начинаем квиз...')
    main_state.add_command(
        Command(
            'choose_lang',
            choose_lang,
            'выбрать другой язык'),
        main_state)
    main_state.add_command(
        Command(
            'show_words',
            show_words,
            'показать изученные слова'),
        main_state)
    main_state.add_command(
        Command(
            'show_quiz_scoreboard',
            show_scoreboard,
            'показать таюлицу рекордов квиза'),
        main_state)
    main_state.add_command(
        Command(
            'status',
            show_status,
            'показать текущие настройки'),
        main_state)
    main_state.add_custom_handler(CallbackQueryHandler(button))

    # fill translating state commands
    translating_state.add_command(
        Command(
            'done',
            null_action,
            'закончить перевод'),
        main_state,
        'Выход из режима переводчика')
    translating_state.add_command(
        Command(
            'status',
            show_status,
            'показать текущие настройки'),
        translating_state)
    translating_state.add_custom_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_for_translate))

    # fill quiz state commands
    quiz_state.add_command(
        Command(
            'done',
            quiz_exit,
            'закончить квиз'),
        main_state,
        'Квиз закончен')
    quiz_state.add_command(
        Command(
            'status',
            show_status,
            'показать текущие настройки'),
        quiz_state)
    quiz_state.add_command(
        Command(
            'next_question',
            quiz_next_quest,
            'попросить еще один вопрос'),
        quiz_state)
    quiz_state.add_custom_handler(CallbackQueryHandler(quiz_answer))

    states_list = [main_state, translating_state, quiz_state]

    return states_list


if __name__ == '__main__':
    # Init repository to store per-user prompted phrases
    word_book = SQLiteRepository('user_phrase_base.db',
                                 'word_book',
                                 {'user_id': 'INTEGER',
                                  'target_lang': 'TEXT',
                                  'phrase': 'TEXT'},
                                 UserTableEntry,
                                 'user_id')

    quiz_scoreboard = SQLiteRepository(
        'quiz_scoreboard.db',
        'quiz_score',
        {
            'user_id': 'INTEGER',
            'user_name': 'TEXT',
            'lang': 'TEXT',
            'score': 'INTEGER'},
        QuizScoreTableEntry,
        'user_id')

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
