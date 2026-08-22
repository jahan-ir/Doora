import customtkinter as ck
from tkinter import messagebox
import tkinter as tk
from PIL import Image
import sqlite3
from datetime import datetime , timedelta , date
import jdatetime
import os
import sys
import threading
import requests
import random as rd

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "tasks.db")
db = sqlite3.connect(DB_PATH)
cur = db.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT,
        date TEXT,
        is_done INTEGER
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS app_status (
        id INTEGER PRIMARY KEY,
        last_check_date TEXT
    )
""")
db.commit()
cur.execute ("""

    CREATE TABLE IF NOT EXISTS Tomorrow(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task text,
    date text,
    is_done INTEGER
    )
""")
db.commit()
cur.execute ("""

    CREATE TABLE IF NOT EXISTS motivation(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text_motivation text
    )
""")
db.commit()
cur.execute("""
    CREATE TABLE IF NOT EXISTS weekly (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT,
        date TEXT,
        is_done INTEGER
    )
""")
db.commit()

def check_yesterday_tasks_before_migration():

    global SHOULD_PUNISH

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute("SELECT last_check_date FROM app_status WHERE id = 1")
    result = cur.fetchone()

    if result and result[0] == today:
        SHOULD_PUNISH = False
        return  # امروز قبلاً بررسی شده

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    cur.execute("SELECT COUNT(*) FROM tasks WHERE date = ? AND is_done = 0", (yesterday,))
    undone_count = cur.fetchone()[0]

    if result:
        cur.execute("UPDATE app_status SET last_check_date = ? WHERE id = 1", (today,))
    else:
        cur.execute("INSERT INTO app_status(id, last_check_date) VALUES(1, ?)", (today,))
    db.commit()

    SHOULD_PUNISH = undone_count > 0


SHOULD_PUNISH = False

def move_tomorrow_tasks_to_today():

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute("SELECT id, task FROM Tomorrow WHERE date = ?", (today,))
    rows = cur.fetchall()

    for tomorrow_id, task_text in rows:
        cur.execute(
            "INSERT INTO tasks(task, date, is_done) VALUES (?, ?, ?)",
            (task_text, today, 0)
        )
        cur.execute("DELETE FROM Tomorrow WHERE id = ?", (tomorrow_id,))

    db.commit()

def gregorian_to_jalali_table_suffix(gregorian_date_str):
    """ '2026-07-30' -> '1405_05_08' (فرمت مناسب برای اسم جدول) """
    year, month, day = map(int, gregorian_date_str.split("-"))
    g_date = datetime(year, month, day)
    j_date = jdatetime.date.fromgregorian(date=g_date)
    return j_date.strftime("%Y_%m_%d")


def migrate_old_tasks_to_daily_tables():#میاد میبینه اگر تسک جدیدی وارد کردی و اون تسک روزش مرتبط با تسک های قبل نبود میاد کل تسک های روز قبل رو وارد یه جدول جدید میکند

    today = datetime.now().strftime("%Y-%m-%d")
    
    cur.execute("SELECT DISTINCT date FROM tasks WHERE date != ?", (today,))
    old_dates = [row[0] for row in cur.fetchall()]
    for old_date in old_dates:
        table_suffix = gregorian_to_jalali_table_suffix(old_date)
        table_name = f"task_{table_suffix}"

        cur.execute(f'''
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                task TEXT,
                is_done INTEGER
            )
        ''')
        #داخل جدول جدید روز و کار و انجام شدنش یا نشدنش رو نشون میده
        cur.execute("SELECT task, is_done FROM tasks WHERE date = ?", (old_date,))
        rows = cur.fetchall()
        for task_text, is_done in rows:
            cur.execute(
                f'INSERT INTO "{table_name}" (task, is_done) VALUES (?, ?)',
                (task_text, is_done)
            )
        
        #تسک ها رو دیلیت میکنه از جدول فعلی که دارد
        cur.execute("DELETE FROM tasks WHERE date = ?", (old_date,))

    db.commit()

def Clear_weekly_tasks():#میاد میبینه اگر تسک جدیدی وارد کردی و اون تسک روزش مرتبط با تسک های قبل نبود میاد کل تسک های روز قبل رو وارد یه جدول جدید میکند

    today = datetime.now().date()

    cur.execute("SELECT MIN(date) FROM weekly")
    result = cur.fetchone()

    # اگر هیچ تسک هفتگی وجود ندارد
    if not result or result[0] is None:
        return

    first_date = datetime.strptime(result[0], "%Y-%m-%d").date()

    # اگر 7 روز یا بیشتر گذشته باشد
    if (today - first_date).days >= 7:
        cur.execute("DELETE FROM weekly")
        db.commit()
        #تسک ها رو دیلیت میکنه از جدول فعلی که دارد

    db.commit()


def get_all_daily_tables():
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE 'task\\_%' ESCAPE '\\'
    """)
    tables = sorted(row[0] for row in cur.fetchall())
    return tables


def cleanup_old_day_tables():
    day_tables = get_all_daily_tables()
    if len(day_tables) > 10:
        tables_to_drop = day_tables[:5]   # ۵ تای قدیمی‌تر (چون مرتب‌شده از قدیم به جدیده)
        for table_name in tables_to_drop:
            cur.execute(f'DROP TABLE "{table_name}"')
        db.commit()


check_yesterday_tasks_before_migration()   # اول (قبل از migrate) چک کن دیروز کاری نصفه مونده یا نه
move_tomorrow_tasks_to_today()  
migrate_old_tasks_to_daily_tables()   # اول کارهای قدیمی رو به جدول روزانه‌شون منتقل کن
cleanup_old_day_tables()   
Clear_weekly_tasks()  
db.commit()


# USER_ID_FILE = "device_id.txt"


# def get_or_create_user_id():
#     if os.path.exists(USER_ID_FILE):
#         with open(USER_ID_FILE, "r", encoding="utf-8-sig") as f:
#             saved_id = f.read().strip()
#             if saved_id:
#                 return saved_id
#     import uuid
#     new_id = str(uuid.uuid4())
#     with open(USER_ID_FILE, "w") as f:
#         f.write(new_id)
#     return new_id

# def collect_all_tasks_summary():#همه داده ها رو میگیره و نسبت به همون به ما جواب میده
#     lines = []

#     today = datetime.now().strftime("%Y-%m-%d")
#     cur.execute("SELECT task, is_done FROM tasks WHERE date = ?", (today,))
#     today_rows = cur.fetchall()
#     if today_rows:
#         lines.append("امروز:")
#         for task_text, is_done in today_rows:
#             status = "انجام‌شده" if is_done else "انجام‌نشده"
#             lines.append(f"- {task_text} ({status})")

#     for table_name in reversed(get_all_daily_tables()):
#         display_date = table_name.replace("task_", "").replace("_", "/")
#         cur.execute(f'SELECT task, is_done FROM "{table_name}"')
#         rows = cur.fetchall()
#         if rows:
#             lines.append(f"\nتاریخ {display_date}:")
#             for task_text, is_done in rows:
#                 status = "انجام‌شده" if is_done else "انجام‌نشده"
#                 lines.append(f"- {task_text} ({status})")

#     if not lines:
#         return "هیچ کاری هنوز ثبت نشده."

#     return "\n".join(lines)


# SERVER_URL = "https://your-server-url.onrender.com"   # بعد از دیپلوی، این آدرس رو با آدرس واقعی سرورت عوض کن


# def ask_OpenAI(user_question, on_success, on_error):#دادن پرامت و نوع جواب دادن به ما

#     tasks_summary = collect_all_tasks_summary()   
#     user_id = get_or_create_user_id()

#     def worker():
#         try:
#             response = requests.post(
#                 f"{SERVER_URL}/ask",
#                 json={
#                     "user_id": user_id,
#                     "tasks_summary": tasks_summary,
#                     "question": user_question
#                 },
#                 timeout=30
#             )
#             data = response.json()

#             if response.status_code != 200:
#                 error_message = data.get("error", "خطای ناشناخته")
#                 app.after(0, lambda: on_error(error_message))
#                 return

#             result_text = data["answer"]
#             app.after(0, lambda: on_success(result_text))
#         except Exception as e:
#             error_message = str(e)   # مقدار رو همینجا توی یه متغیر معمولی نگه می‌داریم
#             app.after(0, lambda: on_error(error_message))

#     threading.Thread(target=worker, daemon=True).start()


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ck.set_appearance_mode("light")

app = ck.CTk()
#ایکون ستینگ سمت چپ پایین
my_image = ck.CTkImage(
    light_image=Image.open(resource_path("Image/settings.png")),
    dark_image=Image.open(resource_path("Image/settings.png")),
    size=(24, 24)
)
#ایکون برنامه
app.wm_iconbitmap(resource_path('Image/to_do.ico'))
app.title('Doora')
app.geometry("930x620")
current_page_widgets = []

def hide_current_page():
    for widget in current_page_widgets:
        widget.pack_forget()
    current_page_widgets.clear()


def loade_page_todo():#صفحه ای که با کلیک روی دکمه تو دو زدن باز بشه
    bottom_bar = ck.CTkFrame(app, fg_color="transparent")

    text_box = ck.CTkEntry( #تکس باکس نوشتن کاری که میخوایی بکنی
        bottom_bar,
        placeholder_text="add the new work ",
        height=40,
        corner_radius=20
    )
    text_box.pack(side="left", fill="x", expand=True) #تکس باکس کجا قرار بگیره

    page = ck.CTkScrollableFrame(app, fg_color="#F5F5F7", corner_radius=20,#صفحه سفید ایجاد کردن مثل یه فرم
                                scrollbar_button_color="#EDEDEE",
                                height=500,
                                width=678)

    title_label1 = ck.CTkLabel(#متن بالای صفحه
        page,
        text="کارهای من",
        text_color="black",
        font=("B Nazanin", 30, "bold")
    )
    title_label1.pack(padx=15, pady=(2, 0), anchor="w")

    title_label = ck.CTkLabel(#متن که زیر کارهای من میاد
        page,
        text="_________________________________________________________________________________________________________________________",
        text_color="black",
        font=("B Nazanin", 20)
    )
    title_label.pack(padx=15, pady=(0, 10), anchor="w",fill="both")
    normal_font = ck.CTkFont(family="B Nazanin", size=16)#تعریف فونت روی یه متغیر که دیگه نیاز نباشه هی نوع فنت دلخواه رو بنویسیم
    done_font = ck.CTkFont(family="B Nazanin", size=16, overstrike=True)
    
    def delete_task(item_frame):#تابع برای زدن دکمه دیلیت بغل کاری که نوشته شده
        cur.execute("DELETE FROM tasks WHERE id = ?", (item_frame.task_id,))
        db.commit()
        item_frame.destroy()

    def create_task_widget(task_id, task_text, is_done):
        item_frame = ck.CTkFrame(page, fg_color="white", corner_radius=12)
        item_frame.task_id = task_id   # id دیتابیس رو روی خودِ ویجت نگه می‌داریم
        item_frame.pack(padx=10, pady=5, fill="x")

        checkbox_var = tk.BooleanVar(value=bool(is_done))

        task_label = ck.CTkLabel(#اگه دکمه زده شده بود فونت رو تغییر بده
            item_frame,
            text=task_text,
            text_color="#9CA3AF" if is_done else "black",
            font=done_font if is_done else normal_font,
            anchor="w"
        )

        def toggle_done():#داخل دیتا بیس تغییر بده بعد زدن چک باکس
            new_state = checkbox_var.get()
            cur.execute(
                "UPDATE tasks SET is_done = ? WHERE id = ?",
                (1 if new_state else 0, item_frame.task_id)
            )
            db.commit()

            if new_state:
                task_label.configure(font=done_font, text_color="#9CA3AF")
            else:
                task_label.configure(font=normal_font, text_color="black")

        checkbox = ck.CTkCheckBox(#تعریف چک باکس
            item_frame,
            text="",
            variable=checkbox_var,
            command=toggle_done,
            width=24,
            checkbox_width=22,
            checkbox_height=22
        )
        checkbox.pack(side="left", padx=(10, 5), pady=10)

        task_label.pack(side="left", padx=5, pady=10, fill="x", expand=True)

        delete_button = ck.CTkButton(#تعریف دکمه حذف
            item_frame,
            text="حذف",
            width=60,
            height=28,
            corner_radius=10,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=lambda: delete_task(item_frame)
        )
        delete_button.pack(side="right", padx=10, pady=10)

    def load_tasks_from_db():
        """موقع باز شدن صفحه، کارهای قبلاً ذخیره‌شده رو از دیتابیس می‌خونه و نشون می‌ده."""
        cur.execute("SELECT id, task, is_done FROM tasks ORDER BY id")
        rows = cur.fetchall()
        for task_id, task_text, is_done in rows:
            create_task_widget(task_id, task_text, is_done)

    load_tasks_from_db()   # همین‌جا صدا زده میشه تا کارهای قبلی نمایش داده بشن

    def add_task_item():
        task_text = text_box.get().strip()
        if task_text == "":
            return
        today = datetime.now().strftime("%Y-%m-%d")
        cur.execute(
            """INSERT INTO tasks(task , date , is_done) VALUES(?,?,?)""",(task_text,today,0)
        )
        db.commit()
        new_task_id = cur.lastrowid
        
        create_task_widget(new_task_id, task_text, 0)

        text_box.delete(0, "end")
        
        
    add_button = ck.CTkButton(#دکمه بقل تکس باکس اد
                bottom_bar,
                text="add",
                width=80,
                height=32,
                corner_radius=15,
                command=add_task_item
            )
    add_button.pack(side="right", padx=(10, 0))
        
    text_box.bind("<Return>", lambda event: add_task_item())

    
    return bottom_bar , page

sidebar = ck.CTkFrame(app, width=200, fg_color="#4C3FCC")#ساخت فارم
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)
def page_todo():
    hide_current_page()
    bottom_bar, page = loade_page_todo()
    bottom_bar.pack(side="bottom", fill="both", padx=20, pady=10)
    page.pack(side="top", anchor="nw", fill="both", expand=True, padx=10, pady=10)
    current_page_widgets.extend([bottom_bar, page])

def load_page_Tomorrow():
    bottom_bar = ck.CTkFrame(app, fg_color="transparent")

    text_box = ck.CTkEntry( #تکس باکس نوشتن کاری که میخوایی بکنی
        bottom_bar,
        placeholder_text="add the new work ",
        height=40,
        corner_radius=20
    )
    text_box.pack(side="left", fill="x", expand=True) #تکس باکس کجا قرار بگیره

    page = ck.CTkScrollableFrame(app, fg_color="#F5F5F7", corner_radius=20,#صفحه سفید ایجاد کردن مثل یه فرم
                                scrollbar_button_color="#EDEDEE",
                                height=500,
                                width=678)

    title_label1 = ck.CTkLabel(#متن بالای صفحه
        page,
        text="کارهای فردا",
        text_color="black",
        font=("B Nazanin", 30, "bold")
    )
    title_label1.pack(padx=15, pady=(2, 0), anchor="w")

    title_label = ck.CTkLabel(#متن که زیر کارهای من میاد
        page,
        text="_________________________________________________________________________________________________________________________",
        text_color="black",
        font=("B Nazanin", 20)
    )
    title_label.pack(padx=15, pady=(0, 10), anchor="w",fill="both")
    normal_font = ck.CTkFont(family="B Nazanin", size=16)#تعریف فونت روی یه متغیر که دیگه نیاز نباشه هی نوع فنت دلخواه رو بنویسیم
    done_font = ck.CTkFont(family="B Nazanin", size=16, overstrike=True)
    
    def delete_task(item_frame):#تابع برای زدن دکمه دیلیت بغل کاری که نوشته شده
        cur.execute("DELETE FROM Tomorrow WHERE id = ?", (item_frame.task_id,))
        db.commit()
        item_frame.destroy()

    def create_task_widget(task_id, task_text, is_done):
        item_frame = ck.CTkFrame(page, fg_color="white", corner_radius=12)
        item_frame.task_id = task_id   # id دیتابیس رو روی خودِ ویجت نگه می‌داریم
        item_frame.pack(padx=10, pady=5, fill="x")

        checkbox_var = tk.BooleanVar(value=bool(is_done))

        task_label = ck.CTkLabel(#اگه دکمه زده شده بود فونت رو تغییر بده
            item_frame,
            text=task_text,
            text_color="#9CA3AF" if is_done else "black",
            font=done_font if is_done else normal_font,
            anchor="w"
        )

        def toggle_done():#داخل دیتا بیس تغییر بده بعد زدن چک باکس
            new_state = checkbox_var.get()
            cur.execute(
                "UPDATE Tomorrow SET is_done = ? WHERE id = ?",
                (1 if new_state else 0, item_frame.task_id)
            )
            db.commit()

            if new_state:
                task_label.configure(font=done_font, text_color="#9CA3AF")
            else:
                task_label.configure(font=normal_font, text_color="black")

        checkbox = ck.CTkCheckBox(#تعریف چک باکس
            item_frame,
            text="",
            variable=checkbox_var,
            command=toggle_done,
            width=24,
            checkbox_width=22,
            checkbox_height=22
        )
        checkbox.pack(side="left", padx=(10, 5), pady=10)

        task_label.pack(side="left", padx=5, pady=10, fill="x", expand=True)

        delete_button = ck.CTkButton(#تعریف دکمه حذف
            item_frame,
            text="حذف",
            width=60,
            height=28,
            corner_radius=10,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=lambda: delete_task(item_frame)
        )
        delete_button.pack(side="right", padx=10, pady=10)

    def load_tasks_from_db():
        """موقع باز شدن صفحه، کارهای قبلاً ذخیره‌شده رو از دیتابیس می‌خونه و نشون می‌ده."""
        cur.execute("SELECT id, task, is_done FROM Tomorrow ORDER BY id")
        rows = cur.fetchall()
        for task_id, task_text, is_done in rows:
            create_task_widget(task_id, task_text, is_done)

    load_tasks_from_db()   # همین‌جا صدا زده میشه تا کارهای قبلی نمایش داده بشن

    def add_task_item():
        task_text = text_box.get().strip()
        if task_text == "":
            return
        yesterday = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        cur.execute(
            """INSERT INTO Tomorrow(task , date , is_done) VALUES(?,?,?)""",(task_text,yesterday,0)
        )
        db.commit()
        new_task_id = cur.lastrowid
        
        create_task_widget(new_task_id, task_text, 0)

        text_box.delete(0, "end")
        
        
    add_button = ck.CTkButton(#دکمه بقل تکس باکس اد
                bottom_bar,
                text="add",
                width=80,
                height=32,
                corner_radius=15,
                command=add_task_item
            )
    add_button.pack(side="right", padx=(10, 0))
        
    text_box.bind("<Return>", lambda event: add_task_item())

    
    return bottom_bar , page

def page_Tomorrow():
    hide_current_page()
    bottom_bar, page = load_page_Tomorrow()
    bottom_bar.pack(side="bottom", fill="both", padx=20, pady=10)
    page.pack(side="top", anchor="nw", fill="both", expand=True, padx=10, pady=10)
    current_page_widgets.extend([bottom_bar, page])

def load_history_page():

    history_page = ck.CTkScrollableFrame(app, fg_color="#F5F5F7", corner_radius=20,
                                          scrollbar_button_color="#EDEDEE",
                                          height=500,
                                          width=678)

    title = ck.CTkLabel(
        history_page,
        text="کارهای روزهای قبل",
        text_color="black",
        font=("B Nazanin", 30, "bold")
    )
    title.pack(padx=15, pady=(15, 5), anchor="w")
    title_label = ck.CTkLabel(
        history_page,
        text="_________________________________________________________________________________________________________________________",
        text_color="black",
        font=("B Nazanin", 20)
    )
    title_label.pack(padx=15, pady=(0, 10), anchor="w", fill="both")
    day_tables = get_all_daily_tables()

    if not day_tables:
        empty_label = ck.CTkLabel(
            history_page,
            text="هنوز آرشیوی وجود نداره",
            text_color="#9CA3AF",
            font=("B Nazanin", 16)
        )
        empty_label.pack(padx=15, pady=20, anchor="w")

    # از جدیدترین جدول به قدیمی‌ترین نمایش بده
    for table_name in reversed(day_tables):

        display_date = table_name.replace("task_", "").replace("_", "/")

        date_label = ck.CTkLabel(
            history_page,
            text=display_date,
            text_color="#4C3FCC",
            font=("B Nazanin", 16, "bold")
        )
        date_label.pack(padx=15, pady=(15, 5), anchor="w")

        cur.execute(f'SELECT task, is_done FROM "{table_name}"')
        rows = cur.fetchall()

        for task_text, is_done in rows:
            status_symbol = "✔" if is_done else "✗"
            status_color = "#22C55E" if is_done else "#9CA3AF"

            row_frame = ck.CTkFrame(history_page, fg_color="white", corner_radius=10)
            row_frame.pack(padx=15, pady=3, fill="x")

            task_label = ck.CTkLabel(
                row_frame,
                text=task_text,
                text_color="black",
                font=("B Nazanin", 14),
                anchor="w"
            )
            task_label.pack(side="left", padx=10, pady=8, fill="x", expand=True)

            status_label = ck.CTkLabel(
                row_frame,
                text=status_symbol,
                text_color=status_color,
                font=("B Nazanin", 16, "bold")
            )
            status_label.pack(side="right", padx=10, pady=8)

    return history_page
 

def page_history():
    hide_current_page()
    history_page = load_history_page()
    history_page.pack(side="top", anchor="nw", fill="both", expand=True, padx=10, pady=10)
    current_page_widgets.append(history_page)



# def loade_AI_page():
#     bottom_bar = ck.CTkFrame(app, fg_color="transparent")

#     text_box = ck.CTkEntry(
#         bottom_bar,
#         placeholder_text="Ask a question.",
#         height=40,
#         corner_radius=20
#     )
#     text_box.pack(side="left", fill="x", expand=True)

#     page = ck.CTkScrollableFrame(app, fg_color="#F5F5F7", corner_radius=20,
#                                 scrollbar_button_color="#EDEDEE",
#                                 height=500,
#                                 width=678)

#     title_label1 = ck.CTkLabel(
#         page,
#         text="سوالت رو از هوش مصنوعی بپرس",
#         text_color="black",
#         font=("B Nazanin", 30, "bold")
#     )
#     title_label1.pack(padx=15, pady=(15, 10), anchor="w")

#     result_box = ck.CTkTextbox(
#         page,
#         fg_color="white",
#         text_color="black",
#         font=("B Nazanin", 15),
#         corner_radius=12,
#         height=380,
#         wrap="word"
#     )
#     result_box.pack(padx=15, pady=10, fill="both", expand=True)
#     result_box.insert("1.0", "سوالت رو بپرس...")
#     result_box.configure(state="disabled")

#     def show_result(text):
#         result_box.configure(state="normal")
#         result_box.delete("1.0", "end")
#         result_box.insert("1.0", text)
#         result_box.configure(state="disabled")
#         add_button.configure(state="normal", text="add")

#     def show_error(error_text):
#         show_result(f"خطا پیش اومد:\n{error_text}\n\nمطمئن شو به اینترنت وصلی.")

#     def add_task_item():
#         task_text = text_box.get().strip()
#         if task_text == "":
#             return

#         add_button.configure(state="disabled", text="در حال فکر کردن...")
#         show_result("در حال ارتباط با هوش مصنوعی...")

#         ask_OpenAI(task_text, show_result, show_error)
#         text_box.delete(0, "end")

#     add_button = ck.CTkButton(
#         bottom_bar,
#         text="Enter",
#         width=80,
#         height=32,
#         corner_radius=15,
#         command=add_task_item
#     )
#     add_button.pack(side="right", padx=(10, 0))

#     text_box.bind("<Return>", lambda event: add_task_item())

#     return bottom_bar, page


# def Open_page_AI():
#     hide_current_page()
#     bottom_bar, page = loade_AI_page()
#     bottom_bar.pack(side="bottom", fill="both", padx=20, pady=10)
#     page.pack(side="top", anchor="nw", fill="both", expand=True, padx=10, pady=10)
#     current_page_widgets.extend([bottom_bar, page])


settings_popup = None   # نگه‌داری وضعیت باز/بسته بودن پاپ‌آپ
 
 
def clear_all_history():
    """همه‌ی جدول‌های روزانه‌ی آرشیو رو Drop می‌کنه و جدول tasks امروز رو هم خالی می‌کنه."""
    confirmed = messagebox.askyesno(
        "پاک کردن کل تاریخچه",
        "مطمئنی می‌خوای همه‌ی کارها (امروز و آرشیو روزهای قبل) رو برای همیشه پاک کنی؟\nاین کار برگشت‌ناپذیره."
    )
    if not confirmed:
        return
 
    # خالی کردن جدول امروز
    cur.execute("DELETE FROM tasks")
 
    # Drop کردن همه‌ی جدول‌های روزانه‌ی آرشیو
    for table_name in get_all_daily_tables():
        cur.execute(f'DROP TABLE "{table_name}"')
 
    db.commit()
 
    close_settings_popup()
 
    # اگه صفحه‌ی فعلی To do یا Current projects بود، دوباره لودش کن تا خالی بودنش نشون داده بشه
    messagebox.showinfo("انجام شد", "کل تاریخچه پاک شد.")
    page_todo()
 
 
def close_settings_popup():
    global settings_popup
    if settings_popup is not None:
        settings_popup.destroy()
        settings_popup = None
 
 
def open_settings_menu():
    global settings_popup
 
    # اگه پاپ‌آپ قبلاً باز بود، دوباره کلیک یعنی ببندش (toggle)
    if settings_popup is not None:
        close_settings_popup()
        return
 
    settings_popup = ck.CTkFrame(app, fg_color="white", corner_radius=12,
                                  border_width=1, border_color="#DDDDDD")
    # درست بالای دکمه‌ی تنظیمات باز میشه
    settings_popup.place(x=10, y=520)
 
    clear_button = ck.CTkButton(
        settings_popup,
        text="پاک کردن کل تاریخچه",
        fg_color="#E74C3C",
        hover_color="#C0392B",
        corner_radius=10,
        width=180,
        height=36,
        command=clear_all_history
    )
    clear_button.pack(padx=10, pady=10)
 
def page_Motivation():
    bottom_bar = ck.CTkFrame(app, fg_color="transparent")

    text_box = ck.CTkEntry( #تکس باکس نوشتن کاری که میخوایی بکنی
        bottom_bar,
        placeholder_text="add the new Motivation ",
        height=40,
        corner_radius=20
    )
    text_box.pack(side="left", fill="x", expand=True) #تکس باکس کجا قرار بگیره

    page = ck.CTkScrollableFrame(app, fg_color="#F5F5F7", corner_radius=20,#صفحه سفید ایجاد کردن مثل یه فرم
                                scrollbar_button_color="#EDEDEE",
                                height=500,
                                width=678)

    title_label1 = ck.CTkLabel(#متن بالای صفحه
        page,
        text="Motivation",
        text_color="black",
        font=("B Nazanin", 30, "bold")
    )
    title_label1.pack(padx=15, pady=(2, 0), anchor="w")

    title_label = ck.CTkLabel(#متن که زیر کارهای من میاد
        page,
        text="_________________________________________________________________________________________________________________________",
        text_color="black",
        font=("B Nazanin", 20)
    )
    title_label.pack(padx=15, pady=(0, 10), anchor="w",fill="both")
    normal_font = ck.CTkFont(family="B Nazanin", size=20)#تعریف فونت روی یه متغیر که دیگه نیاز نباشه هی نوع فنت دلخواه رو بنویسیم
    done_font = ck.CTkFont(family="B Nazanin", size=16, overstrike=True)
    
    def delete_task(item_frame):#تابع برای زدن دکمه دیلیت بغل کاری که نوشته شده
        cur.execute("DELETE FROM Motivation WHERE id = ?", (item_frame.task_id,))
        db.commit()
        item_frame.destroy()

    def create_task_widget(task_id , text_motivation):
        item_frame = ck.CTkFrame(page, fg_color="white", corner_radius=12)
        item_frame.task_id = task_id   # id دیتابیس رو روی خودِ ویجت نگه می‌داریم
        item_frame.pack(padx=10, pady=5, fill="x")
        task_label = ck.CTkLabel(#اگه دکمه زده شده بود فونت رو تغییر بده
            item_frame,
            text= text_motivation,
            font= normal_font,
            anchor="w"
        )
        task_label.pack(side="left", padx=5, pady=10, fill="y", expand=True)
        delete_button = ck.CTkButton(#تعریف دکمه حذف
            item_frame,
            text="حذف",
            width=60,
            height=28,
            corner_radius=10,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=lambda: delete_task(item_frame)
        )
        delete_button.pack(side="right", padx=10, pady=10)


    def load_tasks_from_db():
        """موقع باز شدن صفحه، کارهای قبلاً ذخیره‌شده رو از دیتابیس می‌خونه و نشون می‌ده."""
        cur.execute("SELECT id , text_motivation FROM Motivation ORDER BY id")
        rows = cur.fetchall()
        for task_id , text_motivation in rows:
            create_task_widget( task_id , text_motivation )

    load_tasks_from_db()   # همین‌جا صدا زده میشه تا کارهای قبلی نمایش داده بشن

    def add_task_item():
        text_motivation = text_box.get().strip()
        if text_motivation == "":
            return
        cur.execute(
            """INSERT INTO Motivation(text_motivation) VALUES(?)""",(text_motivation,)
        )
        db.commit()
        new_task_id = cur.lastrowid
        
        create_task_widget(new_task_id , text_motivation)

        text_box.delete(0, "end")
        
    add_button = ck.CTkButton(#دکمه بقل تکس باکس اد
                bottom_bar,
                text="add",
                width=80,
                height=32,
                corner_radius=15,
                command=add_task_item
            )
    add_button.pack(side="right", padx=(10, 0))
        
    text_box.bind("<Return>", lambda event: add_task_item())
    return bottom_bar , page

def load_page_Motivation():
    hide_current_page()
    bottom_bar, page = page_Motivation()
    bottom_bar.pack(side="bottom", fill="both", padx=20, pady=10)
    page.pack(side="top", anchor="nw", fill="both", expand=True, padx=10, pady=10)
    current_page_widgets.extend([bottom_bar, page])
def page_weekly():#صفحه ای که با کلیک روی دکمه تو دو زدن باز بشه
    bottom_bar = ck.CTkFrame(app, fg_color="transparent")

    text_box = ck.CTkEntry( #تکس باکس نوشتن کاری که میخوایی بکنی
        bottom_bar,
        placeholder_text="add the new work ",
        height=40,
        corner_radius=20
    )
    text_box.pack(side="left", fill="x", expand=True) #تکس باکس کجا قرار بگیره

    page = ck.CTkScrollableFrame(app, fg_color="#F5F5F7", corner_radius=20,#صفحه سفید ایجاد کردن مثل یه فرم
                                scrollbar_button_color="#EDEDEE",
                                height=500,
                                width=678)

    title_label1 = ck.CTkLabel(#متن بالای صفحه
        page,
        text="کارهای هفتگی",
        text_color="black",
        font=("B Nazanin", 30, "bold")
    )
    title_label1.pack(padx=15, pady=(2, 0), anchor="w")

    title_label = ck.CTkLabel(#متن که زیر کارهای من میاد
        page,
        text="_________________________________________________________________________________________________________________________",
        text_color="black",
        font=("B Nazanin", 20)
    )
    title_label.pack(padx=15, pady=(0, 10), anchor="w",fill="both")
    normal_font = ck.CTkFont(family="B Nazanin", size=16)#تعریف فونت روی یه متغیر که دیگه نیاز نباشه هی نوع فنت دلخواه رو بنویسیم
    done_font = ck.CTkFont(family="B Nazanin", size=16, overstrike=True)
    
    def delete_task(item_frame):#تابع برای زدن دکمه دیلیت بغل کاری که نوشته شده
        cur.execute("DELETE FROM weekly WHERE id = ?", (item_frame.task_id,))
        db.commit()
        item_frame.destroy()

    def create_task_widget(task_id, task_text, is_done):
        item_frame = ck.CTkFrame(page, fg_color="white", corner_radius=12)
        item_frame.task_id = task_id   # id دیتابیس رو روی خودِ ویجت نگه می‌داریم
        item_frame.pack(padx=10, pady=5, fill="x")

        checkbox_var = tk.BooleanVar(value=bool(is_done))

        task_label = ck.CTkLabel(#اگه دکمه زده شده بود فونت رو تغییر بده
            item_frame,
            text=task_text,
            text_color="#9CA3AF" if is_done else "black",
            font=done_font if is_done else normal_font,
            anchor="w"
        )

        def toggle_done():#داخل دیتا بیس تغییر بده بعد زدن چک باکس
            new_state = checkbox_var.get()
            cur.execute(
                "UPDATE weekly SET is_done = ? WHERE id = ?",
                (1 if new_state else 0, item_frame.task_id)
            )
            db.commit()

            if new_state:
                task_label.configure(font=done_font, text_color="#9CA3AF")
            else:
                task_label.configure(font=normal_font, text_color="black")

        checkbox = ck.CTkCheckBox(#تعریف چک باکس
            item_frame,
            text="",
            variable=checkbox_var,
            command=toggle_done,
            width=24,
            checkbox_width=22,
            checkbox_height=22
        )
        checkbox.pack(side="left", padx=(10, 5), pady=10)

        task_label.pack(side="left", padx=5, pady=10, fill="x", expand=True)

        delete_button = ck.CTkButton(#تعریف دکمه حذف
            item_frame,
            text="حذف",
            width=60,
            height=28,
            corner_radius=10,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=lambda: delete_task(item_frame)
        )
        delete_button.pack(side="right", padx=10, pady=10)

    def load_tasks_from_db():
        """موقع باز شدن صفحه، کارهای قبلاً ذخیره‌شده رو از دیتابیس می‌خونه و نشون می‌ده."""
        cur.execute("SELECT id, task, is_done FROM weekly ORDER BY id")
        rows = cur.fetchall()
        for task_id, task_text, is_done in rows:
            create_task_widget(task_id, task_text, is_done)

    load_tasks_from_db()   # همین‌جا صدا زده میشه تا کارهای قبلی نمایش داده بشن

    def add_task_item():
        task_text = text_box.get().strip()
        if task_text == "":
            return
        today = datetime.now().strftime("%Y-%m-%d")
        cur.execute(
            """INSERT INTO weekly(task , date , is_done) VALUES(?,?,?)""",(task_text,today,0)
        )
        db.commit()
        new_task_id = cur.lastrowid
        
        create_task_widget(new_task_id, task_text, 0)

        text_box.delete(0, "end")
        
        
    add_button = ck.CTkButton(#دکمه بقل تکس باکس اد
                bottom_bar,
                text="add",
                width=80,
                height=32,
                corner_radius=15,
                command=add_task_item
            )
    add_button.pack(side="right", padx=(10, 0))
        
    text_box.bind("<Return>", lambda event: add_task_item())
    
    return bottom_bar , page

def loade_page_weekly():
    hide_current_page()
    bottom_bar, page = page_weekly()
    bottom_bar.pack(side="bottom", fill="both", padx=20, pady=10)
    page.pack(side="top", anchor="nw", fill="both", expand=True, padx=10, pady=10)
    current_page_widgets.extend([bottom_bar, page])

for name in ["My Tasks", "Tasks Tomorrow", "Tasks Weekly" ,"Current projects","Motivation"]:#ساخت دکمه های سمت چپ فرم 
    if name == "My Tasks":
        command_func = page_todo

    elif name == "Current projects":
        command_func = page_history

    # elif name == "AI":
    #     command_func = Open_page_AI

    elif name == "Tasks Tomorrow":
        command_func = page_Tomorrow

    elif name == "Tasks Weekly":
            command_func = loade_page_weekly

    else:
        command_func = load_page_Motivation

    btn = ck.CTkButton(
        sidebar,
        text=name,
        anchor="w",
        corner_radius=15,
        fg_color="transparent",
        hover_color="#5C4FD0",
        text_color="white",
        font=("Arial", 14),
        height=45,
        command=command_func
    )
    btn.pack(padx=15, pady=5, fill="x")

img_btn = ck.CTkButton(#ساخت دکمه که روش عکس تنظیمات هستش
    sidebar,              
    text='',
    corner_radius=15,
    image=my_image,
    fg_color="transparent",
    hover_color="#5C4FD0",
    text_color="white",
    width=45,
    height=45,
    command=open_settings_menu
)

img_btn.pack(padx=15, pady=5, anchor="w")  
img_btn.place(x=10, y=570)
def Punishment():
    hide_current_page()
    sidebar.pack_forget()
    punishment_list = [
    "شنا 100 تا",
    "به خیریه کمک کردن 100 هزار تومن",
    "تماس با یکی و گفتن که من برنامه امروزم رو انجام ندادم",
    "اسکات 400 تا",
    "دراز نشست 100 تا",
    "گوشی 4 ساعت خاموش",
    "امروز از رفتن به شبکه های اجتماعی محرومی",
    "امروز باید ناهار بزاری",
    "خونه رو تمیز کن",
    "بنویسی چرا کارم رو انجام ندادم حداقل 7 خط",
    "دوش اب سرد 5 دیقه",
    "یه ویس گرفتن و بدون بهونه گفتن چرا کار رو انجام ندادی 5 بار گوش میکنی",
    "همین الان باید 1 ساعت درس بخونی(هر درسی که خودت دوست داری)",
    "همین الان 4 لیوان اب بخور",
]
    random_Punishment = (rd.choice(punishment_list))
    page = ck.CTkScrollableFrame(
    app,
    fg_color="#F5F5F7",
    corner_radius=20,
    scrollbar_button_color="#EDEDEE"
    )
    page.pack(side="top", anchor="nw", fill="both", expand=True, padx=10, pady=10)
    current_page_widgets.append(page)

# عنوان
    ck.CTkLabel(
    page,
    text="⚠️ DAILY PUNISHMENT ⚠️",
    font=("Arial", 30, "bold"),
    text_color="#D32F2F"
).pack(pady=(20, 10))

# خط جداکننده
    ck.CTkFrame(
    page,
    height=2,
    fg_color="#D0D0D0"
).pack(fill="x", padx=20, pady=(0, 25))

# کادر تنبیه
    punishment_frame = ck.CTkFrame(
    page,
    fg_color="#FFFFFF",
    corner_radius=20,
    border_width=2,
    border_color="#E53935"
)   
    punishment_frame.pack(fill="x", padx=40, pady=10)

    ck.CTkLabel(
    punishment_frame,
    text=random_Punishment,
    font=("B Nazanin", 32),
    text_color="#202020",
    wraplength=550,
    justify="center"
).pack(padx=30, pady=35)

# دکمه
    button_submit = ck.CTkButton(
    page,
    text="✅ انجام دادم",
    width=220,
    height=55,
    corner_radius=18,
    fg_color="#2E7D32",
    hover_color="#1B5E20",
    font=("Arial", 18, "bold"),
    command=show_menu
)
    button_submit.pack(pady=35)
    warning_frame = ck.CTkFrame(
    page,
    fg_color="#FFF4E5",
    border_width=2,
    border_color="#FF9800",
    corner_radius=15
)
    warning_frame.pack(fill="x", padx=40, pady=(20, 10))

    ck.CTkLabel(
    warning_frame,
    text=(
        "⚠️ یادت باشه!\n"
        "اگر این تنبیه را انجام ندهی، یعنی خودت تصمیم گرفته‌ای "
        "به قولی که به خودت داده‌ای پایبند نباشی. "
        "و توی زندگیت به هیچ جایی نمیرسی چون ضعیفی"
    ),
    font=("B Nazanin", 22),
    text_color="#5D4037",
    wraplength=600,
    justify="right"
).pack(padx=20, pady=20)

def show_menu():
    hide_current_page()     
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)
    page_todo()   

if SHOULD_PUNISH == True:
    Punishment()
else:
    page_todo()


app.mainloop()