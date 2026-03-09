import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import database

# Загружаем переменные окружения
load_dotenv()

# Получаем токен
TOKEN = os.getenv("BOT_TOKEN")

# Эмодзи для участников (фиксированный порядок)
EMOJIS = ["❤️", "🔥", "⚡", "👾", "💋"]

# Состояния FSM
class GiveawayStates(StatesGroup):
    waiting_for_usernames = State()
    waiting_for_type = State()
    waiting_for_prize = State()
    waiting_for_invite_link = State()
    waiting_for_end_time = State()

async def main():
    if not TOKEN or TOKEN == "your_telegram_bot_token_here":
        print("Ошибка: Токен бота не найден. Проверьте .env файл.")
        return

    # Инициализация БД
    database.init_db()

    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # --- Хендлеры для удаления сообщений о выходе ---
    @dp.message(F.left_chat_member)
    async def on_user_left(message: Message):
        try:
            await message.delete()
            logging.info(f"Удалено сообщение о выходе: {message.left_chat_member.full_name}")
        except Exception as e:
            logging.error(f"Не удалось удалить сообщение: {e}")

    # --- Хендлеры для создания розыгрыша (/tutty) ---

    @dp.message(Command("tutty"))
    async def cmd_tutty(message: Message, state: FSMContext):
        await message.answer("Введите 5 юзернеймов участников (через пробел или с новой строки):\nНапример: @user1 @user2 @user3 @user4 @user5")
        await state.set_state(GiveawayStates.waiting_for_usernames)

    @dp.message(GiveawayStates.waiting_for_usernames)
    async def process_usernames(message: Message, state: FSMContext):
        text = message.text.replace("\n", " ")
        usernames = [u.strip() for u in text.split() if u.strip()]
        
        if len(usernames) != 5:
            await message.answer(f"Нужно ввести ровно 5 юзернеймов! Вы ввели: {len(usernames)}.")
            return

        await state.update_data(usernames=usernames)
        await message.answer("Введите тип розыгрыша (например: 'Пятый поток' или 'ФИНАЛ'):")
        await state.set_state(GiveawayStates.waiting_for_type)

    @dp.message(GiveawayStates.waiting_for_type)
    async def process_type(message: Message, state: FSMContext):
        await state.update_data(giveaway_type=message.text)
        await message.answer("Введите приз (например: 'ОДНОРАЗКУ COOLPLAY'):")
        await state.set_state(GiveawayStates.waiting_for_prize)

    @dp.message(GiveawayStates.waiting_for_prize)
    async def process_prize(message: Message, state: FSMContext):
        await state.update_data(prize=message.text)
        await message.answer("Введите ссылку для приглашения:")
        await state.set_state(GiveawayStates.waiting_for_invite_link)

    @dp.message(GiveawayStates.waiting_for_invite_link)
    async def process_invite_link(message: Message, state: FSMContext):
        await state.update_data(invite_link=message.text)
        await message.answer("Введите дату окончания (текстом, например: '09.03.26 в 12:00'):")
        await state.set_state(GiveawayStates.waiting_for_end_time)

    @dp.message(GiveawayStates.waiting_for_end_time)
    async def process_end_time(message: Message, state: FSMContext):
        data = await state.get_data()
        end_time = message.text
        usernames = data['usernames']
        g_type = data['giveaway_type']
        prize = data['prize']
        invite_link = data['invite_link']
        
        # Сохраняем в БД
        # Сначала создаем запись розыгрыша
        giveaway_id = database.create_giveaway(message.chat.id, prize, invite_link, g_type, end_time)
        
        # Добавляем участников
        for i, username in enumerate(usernames):
            database.add_participant(giveaway_id, username, EMOJIS[i])

        # Формируем сообщение
        text_lines = [
            "TUTTI FRUTTY",
            f"🎉 {g_type.upper()} НА {prize.upper()}",
            "",
        ]
        
        # Список участников для текста
        # В примере: Emoji @username " (кавычки? или просто пусто)
        # Сделаем красиво
        # Используем code block или quote для списка, как на скрине
        # На скрине это выглядит как цитата (вертикальная черта слева)
        
        participants_text = ""
        for i, u in enumerate(usernames):
            participants_text += f"{EMOJIS[i]} {u}\n"
            
        # Оборачиваем в цитату (Markdown V2 > или HTML <blockquote>? Aiogram по дефолту HTML или MD?)
        # По дефолту None, лучше использовать HTML
        
        text_lines.append("<blockquote>")
        text_lines.append(participants_text.strip())
        text_lines.append("</blockquote>")
        text_lines.append("")
        
        text_lines.append("💥 Ссылка для приглашения")
        text_lines.append(invite_link)
        text_lines.append("")
        text_lines.append(f"⏳ Окончание розыгрыша: {end_time}")
        text_lines.append("")
        text_lines.append("Также не забывайте, что заказать одноразки, жидкости,")
        text_lines.append("расходники и многое другое можно в нашем боте.")
        text_lines.append("🤖 Бот: @tuti_frutiiiBot")
        text_lines.append("👤 Менеджер: @tuttifruttymngr")

        full_text = "\n".join(text_lines)

        # Клавиатура
        kb = generate_keyboard(giveaway_id)

        await message.answer(full_text, reply_markup=kb, parse_mode="HTML")
        await state.clear()


    # --- Callback для голосования ---
    @dp.callback_query(F.data.startswith("vote:"))
    async def on_vote(callback: CallbackQuery):
        # data format: vote:giveaway_id:participant_id
        _, g_id, p_id = callback.data.split(":")
        giveaway_id = int(g_id)
        participant_id = int(p_id)
        user_id = callback.from_user.id

        # Проверка на повторное голосование
        if database.has_user_voted(user_id, giveaway_id):
            await callback.answer("Вы уже голосовали в этом розыгрыше!", show_alert=True)
            return

        # Записываем голос
        success = database.vote_for_participant(user_id, giveaway_id, participant_id)
        if success:
            await callback.answer("Ваш голос учтен!")
            # Обновляем клавиатуру с новыми цифрами
            new_kb = generate_keyboard(giveaway_id)
            try:
                await callback.message.edit_reply_markup(reply_markup=new_kb)
            except Exception:
                pass # Если ничего не изменилось (редкий кейс)
        else:
            await callback.answer("Ошибка при голосовании.", show_alert=True)

    print("Бот запущен...")
    await dp.start_polling(bot)

def generate_keyboard(giveaway_id):
    participants = database.get_participants(giveaway_id)
    # participants: list of tuples (id, g_id, username, emoji, votes)
    # id is index 0, emoji is index 3, votes is index 4
    
    buttons = []
    # Сделаем в один ряд или несколько?
    # На скрине кнопки в ряд: "Fire 195", "Lightning 171", etc.
    # Если 5 кнопок, лучше в 1 или 2 ряда.
    # Aiogram builder
    
    row = []
    for p in participants:
        p_id = p[0]
        emoji = p[3]
        votes = p[4]
        text = f"{emoji} {votes}"
        row.append(InlineKeyboardButton(text=text, callback_data=f"vote:{giveaway_id}:{p_id}"))
    
    return InlineKeyboardMarkup(inline_keyboard=[row])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
