import os
import requests
import pandas as pd

import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import aiohttp
import asyncio

# ----------------------
#  Константы и настройки
# ----------------------

BUSINESS_HTTP_BASE = "http://127.0.0.1:8000"

# «Концептуальные» установки с портами (raw, true)
INSTALLATIONS = {
    "Установка 1": (8092, 8093),
    "Установка 2": (8094, 8095),
}

# ------------------
#  Инициализация Dash
# ----------------------

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
server = app.server

RECIEVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Reciever")
BUSINESS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Business")


# ----------------------
#  Вспомогательная функция: список признаков из «длинного» CSV
# ----------------------

def get_feature_options(raw_port: int):
    """
    Читает только шапку из Reciever/data_port_<raw_port>_long.csv (nrows=0),
    исключает 'DateTime' и возвращает [{"label":col,"value":col}, ...].
    Если файла нет или не удалось — [].
    """
    path = os.path.join(RECIEVER_DIR, f"data_port_{raw_port}_long.csv")
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, nrows=0)
            cols = [c for c in df.columns if c != "DateTime"]
            return [{"label": c, "value": c} for c in cols]
        except:
            return []
    return []


# ----------------------
#  Layout
# ----------------------

app.layout = html.Div([
    dbc.Row([
        # ===========================================
        #  Левое меню: выбор установки, интервала, признака, диапазона
        # ===========================================
        dbc.Col([
            html.H2("Панель управления", style={"marginBottom": "1rem", "color": "white"}),

            # 1) Выбор «концептуальной» установки
            html.Div([
                dbc.Label("Выберите установку", style={"color": "white"}),
                dcc.Dropdown(
                    id="dropdown-installation",
                    options=[{"label": k, "value": k} for k in INSTALLATIONS.keys()],
                    value="Установка 1",
                    clearable=False,
                    style={"backgroundColor": "white", "color": "black"},
                    className="mb-4"
                ),
            ]),

            # 2) Интервал интерполяции (мс)
            html.Div([
                dbc.Label("Интервал интерполяции (мс)", style={"color": "white"}),
                dbc.Input(
                    id="input-interval",
                    type="number",
                    min=100,
                    step=100,
                    value=5000,
                    style={"backgroundColor": "#1A2138", "color": "white", "borderColor": "#444"}
                ),
                dbc.Button(
                    "Применить интервал",
                    id="btn-apply-interval",
                    color="primary",
                    className="mt-2"
                ),
                html.Div(
                    id="apply-interval-msg",
                    style={"marginTop": "0.5rem", "color": "#FFD700"}
                ),
            ], className="mb-4"),

            # 3) Выбор признака
            html.Div([
                dbc.Label("Выберите признак", style={"color": "white"}),
                dcc.Dropdown(
                    id="dropdown-feature",
                    options=[],   # заполняется динамически
                    value=None,
                    clearable=False,
                    style={"backgroundColor": "white", "color": "black"},
                    className="mb-4"
                ),
            ]),

            # 4) Диапазон дат (необязательно)
            html.Div([
                dbc.Label("Диапазон дат ", style={"color": "white"}),
                dcc.DatePickerRange(
                    id="date-picker",
                    start_date=None,
                    end_date=None,
                    display_format="YYYY-MM-DD",
                    style={"backgroundColor": "#1A2138", "color": "white"},
                    className="mb-4"
                ),
            ]),

            # 5) Статус соединения / сбора данных
            html.Div(
                id="status-message",
                style={"marginTop": "1rem", "color": "#FFD700", "minHeight": "1.5rem"}
            ),

        ], width=3, style={"padding": "1rem", "backgroundColor": "#1A2138", "height": "100vh"}),

        # ===========================================
        #  Правая часть: три графика, метрика, инфо о записях, таблицы out и metrics-файлов
        # ===========================================
        dbc.Col([
            # —————————————————————————————————————————
            # График 1: «сырые» данные (raw_port)
            # —————————————————————————————————————————
            html.H4("Сырые данные", style={"color": "white"}),
            dcc.Graph(
                id="line-chart-raw",
                style={"height": "25vh"}
            ),

            html.Hr(style={"borderColor": "#444"}),

            # —————————————————————————————————————————
            # График 2: «истинные» данные без пропусков (filled_port long)
            # —————————————————————————————————————————
            html.H4("Истинные данные", style={"color": "white", "marginTop": "1rem"}),
            dcc.Graph(
                id="line-chart-filled",
                style={"height": "25vh"}
            ),

            html.Hr(style={"borderColor": "#444", "marginTop": "1rem"}),

            # —————————————————————————————————————————
            # График 3: «заполненные» данные из бизнеса (data_out_<filled_port>_long.csv)
            # —————————————————————————————————————————
            html.H4("Заполненные данные", style={"color": "white", "marginTop": "1rem"}),
            dcc.Graph(
                id="line-out-long",
                style={"height": "25vh"}
            ),

            html.Hr(style={"borderColor": "#444", "marginTop": "1rem"}),

            # —————————————————————————————————————————
            # Блок «Метрика модели» (последняя строчка из metrics)
            # —————————————————————————————————————————
            html.H4("Метрика работы модели", style={"color": "white", "marginTop": "1rem"}),
            html.Div(id="metrics-info", style={"color": "white", "marginBottom": "1rem"}),

            # —————————————————————————————————————————
            # Информация о «записях» заполненных данных
            # —————————————————————————————————————————
            html.H4("Информация о записях", style={"color": "white", "marginTop": "1rem"}),
            html.Div(id="data-info", style={"color": "white", "marginBottom": "1rem"}),

            # ———————————————————————————————
            # Таблица «out»-файла (результат батчей)
            # —————————————————————————————————————————
            html.H4("Таблица обработки батча", style={"color": "white", "marginTop": "1rem"}),
            dash_table.DataTable(
                id="out-table",
                columns=[
                    {"name": "DateTime", "id": "DateTime"},
                    {"name": "Input", "id": "input"},
                    {"name": "Value", "id": "value"},
                ],
                data=[],
                page_size=10,
                style_header={"backgroundColor": "#1A2138", "color": "white"},
                style_cell={"backgroundColor": "#202946", "color": "white", "textAlign": "left"},
                style_table={"overflowX": "auto"},
            ),

            html.Hr(style={"borderColor": "#444", "marginTop": "1rem"}),

            # —————————————————————————————————————————
            # Таблица «metrics»-файла (вся история метрик из Business)
            # —————————————————————————————————————————
            html.H4("Таблица metrics (история метрик)", style={"color": "white", "marginTop": "1rem"}),
            dash_table.DataTable(
                id="metrics-file-table",
                columns=[],  # будем заполнять динамически
                data=[],
                page_size=10,
                style_header={"backgroundColor": "#1A2138", "color": "white"},
                style_cell={"backgroundColor": "#202946", "color": "white", "textAlign": "left"},
                style_table={"overflowX": "auto"},
            ),

            # —————————————————————————————————————————
            # Интервал опроса (каждые 2000 мс)
            # —————————————————————————————————————————
            dcc.Interval(
                id="interval-update",
                interval=2000,
                n_intervals=0
            ),
        ], width=9, style={"padding": "1rem"}),
    dcc.Store(id="metrics-history", data=[]),
    ])
])


# ----------------------
#  Callback 1: Обновляем список признаков (dropdown-feature)
# ----------------------

@app.callback(
    Output("dropdown-feature", "options"),
    Output("dropdown-feature", "value"),
    Input("dropdown-installation", "value"),
    Input("interval-update", "n_intervals"),
    State("dropdown-feature", "value"),
)
def update_feature_options(inst, n_intervals, current_feature):
    raw_port, _ = INSTALLATIONS[inst]
    opts = get_feature_options(raw_port)
    values = [opt["value"] for opt in opts]

    if current_feature and current_feature in values:
        return opts, current_feature

    default = values[0] if values else None
    return opts, default


# ----------------------
#  Callback 2: «Применить интервал» для всех портов
# ----------------------

async def interval_send(new_interval):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{BUSINESS_HTTP_BASE}/set_interval",
                json={"period_ms": new_interval}
        ) as response:
            return response

@app.callback(
    Output("apply-interval-msg", "children"),
    Input("btn-apply-interval", "n_clicks"),
    State("input-interval", "value"),
)
def apply_interval_all_ports(n_clicks, new_interval):
    if not n_clicks:
        return ""
    try:
        r = asyncio.run(interval_send(new_interval))
        if r.ok:
            return f"Применено: интервал={new_interval} мс для всех портов"
        else:
            return "Ошибка при применении интервала"
    except Exception as e:
        return f"Ошибка: {e}"


# ----------------------
#  Callback 3: Строим три графика, метрику, таблицу «out» и таблицу «metrics»
# ----------------------

df_out = None
df_input = None

@app.callback(
    Output("line-chart-raw", "figure"),
    Output("line-chart-filled", "figure"),
    Output("line-out-long", "figure"),
    Output("metrics-info", "children"),
    Output("data-info", "children"),
    Output("status-message", "children"),
    Output("out-table", "data"),
    Output("metrics-file-table", "columns"),
    Output("metrics-file-table", "data"),
    Output("metrics-history", "data"), 
    Input("interval-update", "n_intervals"),
    State("dropdown-installation", "value"),
    State("dropdown-feature", "value"),
    State("date-picker", "start_date"),
    State("date-picker", "end_date"),
    State("metrics-history", "data"),  
)
def update_visualization(n_intervals, inst, feature, start_date, end_date, metrics_history):
    # Если не задана установка — ничего не рисуем
    if not inst:
        return {}, {}, {}, "", "", "", [], [], []

    raw_port, true_port = INSTALLATIONS[inst]

    # Пути к файловым источникам
    raw_path = os.path.join(RECIEVER_DIR, f"data_port_{raw_port}_long.csv")
    true_long_path = os.path.join(RECIEVER_DIR, f"data_port_{true_port}_long.csv")
    input_path = os.path.join(RECIEVER_DIR, f"data_port_{raw_port}.csv")
    filled_business_long = os.path.join(BUSINESS_DIR, f"data_out_{true_port}_long.csv")
    out_path = os.path.join(BUSINESS_DIR, f"data_out_{true_port}.csv")
    metrics_path = os.path.join(BUSINESS_DIR, f"data_metrics_{true_port}.csv")

    # 1) Если нет «длинного» raw – рисуем «пусто»
    if not os.path.exists(raw_path):
        return {}, {}, {}, "", "", "", [], [], []

    # 2) Читаем raw_long
    try:
        df_long = pd.read_csv(raw_path)
    except:
        return {}, {}, {}, "", "", "Ошибка при чтении raw CSV", [], [], []

    # Если все DateTime пусты → «Потеря соединения»
    if df_long["DateTime"].isnull().all():
        return {}, {}, {}, "", "", "Потеря соединения с установкой", [], [], []

    # 3) Фильтруем по дате для сырых
    dff_raw = df_long.copy()
    if start_date:
        dff_raw = dff_raw[dff_raw["DateTime"] >= start_date]
    if end_date:
        dff_raw = dff_raw[dff_raw["DateTime"] <= end_date]

    # 4) Если feature не в колонках или dff_raw.empty → «Нет данных»
    if not feature or feature not in dff_raw.columns or dff_raw.empty:
        return {}, {}, {}, "", "", "Нет данных для выбранного признака/диапазона", [], [], [], []

    # 5) Строим график 1: «сырые» данные
    fig_raw = {
        "data": [{
            "x": dff_raw["DateTime"],
            "y": dff_raw[feature],
            "type": "line",
            "name": f"raw: {feature}",
            "line": {"color": "#FFD700"}
        }],
        "layout": {
            "title": {"text": f"{inst} – сырые '{feature}'", "font": {"color": "white"}},
            "paper_bgcolor": "#1A2138",
            "plot_bgcolor": "#202946",
            "font": {"color": "white"},
            "xaxis": {"color": "white", "gridcolor": "#444"},
            "yaxis": {"color": "white", "gridcolor": "#444"},
            "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
        }
    }

    # 6) Строим график 2: «истинные» данные без пропусков (true_long)
    fig_filled = {
        "data": [],
        "layout": {
            "title": {"text": "Нет данных без пропусков", "font": {"color": "white"}},
            "paper_bgcolor": "#1A2138",
            "plot_bgcolor": "#202946",
            "font": {"color": "white"},
            "xaxis": {"color": "white", "gridcolor": "#444"},
            "yaxis": {"color": "white", "gridcolor": "#444"},
            "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
        }
    }

    data_info = ""
    out_table_data = []

    if os.path.exists(true_long_path):
        try:
            df_true_long = pd.read_csv(true_long_path)
            dff_true = df_true_long.copy()
            if start_date:
                dff_true = dff_true[dff_true["DateTime"] >= start_date]
            if end_date:
                dff_true = dff_true[dff_true["DateTime"] <= end_date]

            if feature in dff_true.columns:
                used_true_col = feature
                y_true = dff_true[used_true_col]
            else:
                candidates_true = [c for c in dff_true.columns if c != "DateTime"]
                if candidates_true:
                    used_true_col = candidates_true[0]
                    y_true = dff_true[used_true_col]
                else:
                    used_true_col = None
                    y_true = []

            if not dff_true.empty and used_true_col:
                fig_filled = {
                    "data": [{
                        "x": dff_true["DateTime"],
                        "y": y_true,
                        "type": "line",
                        "name": f"true: {used_true_col}",
                        "line": {"color": "#00FF00"}
                    }],
                    "layout": {
                        "title": {"text": f"{inst} – без пропусков '{used_true_col}'", "font": {"color": "white"}},
                        "paper_bgcolor": "#1A2138",
                        "plot_bgcolor": "#202946",
                        "font": {"color": "white"},
                        "xaxis": {"color": "white", "gridcolor": "#444"},
                        "yaxis": {"color": "white", "gridcolor": "#444"},
                        "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
                    }
                }
            else:
                data_info = "Нет данных без пропусков"
        except:
            fig_filled = {
                "data": [],
                "layout": {
                    "title": {"text": "Ошибка чтения true CSV", "font": {"color": "white"}},
                    "paper_bgcolor": "#1A2138",
                    "plot_bgcolor": "#202946",
                    "font": {"color": "white"},
                    "xaxis": {"color": "white", "gridcolor": "#444"},
                    "yaxis": {"color": "white", "gridcolor": "#444"},
                    "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
                }
            }
    else:
        fig_filled = {
            "data": [],
            "layout": {
                "title": {"text": "Нет файла с истинными данными", "font": {"color": "white"}},
                "paper_bgcolor": "#1A2138",
                "plot_bgcolor": "#202946",
                "font": {"color": "white"},
                "xaxis": {"color": "white", "gridcolor": "#444"},
                "yaxis": {"color": "white", "gridcolor": "#444"},
                "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
            }
        }

    # 7) Строим график 3: «заполненные» данные из бизнеса (data_out_<true_port>_long.csv)
    fig_out_long = {
        "data": [],
        "layout": {
            "title": {"text": "Нет заполненных данных из Business", "font": {"color": "white"}},
            "paper_bgcolor": "#1A2138",
            "plot_bgcolor": "#202946",
            "font": {"color": "white"},
            "xaxis": {"color": "white", "gridcolor": "#444"},
            "yaxis": {"color": "white", "gridcolor": "#444"},
            "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
        }
    }

    if os.path.exists(filled_business_long):
        try:
            df_out_long = pd.read_csv(filled_business_long)
            dff_out_long = df_out_long.copy()
            if start_date:
                dff_out_long = dff_out_long[dff_out_long["DateTime"] >= start_date]
            if end_date:
                dff_out_long = dff_out_long[dff_out_long["DateTime"] <= end_date]

            if feature in dff_out_long.columns:
                used_out_col = feature
                y_out_long = dff_out_long[used_out_col]
            else:
                candidates_out_long = [c for c in dff_out_long.columns if c != "DateTime"]
                if candidates_out_long:
                    used_out_col = candidates_out_long[0]
                    y_out_long = dff_out_long[used_out_col]
                else:
                    used_out_col = None
                    y_out_long = []

            if not dff_out_long.empty and used_out_col:
                fig_out_long = {
                    "data": [{
                        "x": dff_out_long["DateTime"],
                        "y": y_out_long,
                        "type": "line",
                        "name": f"business filled: {used_out_col}",
                        "line": {"color": "#FF0000"}
                    }],
                    "layout": {
                        "title": {"text": f"{inst} – заполненные из Business '{used_out_col}'", "font": {"color": "white"}},
                        "paper_bgcolor": "#1A2138",
                        "plot_bgcolor": "#202946",
                        "font": {"color": "white"},
                        "xaxis": {"color": "white", "gridcolor": "#444"},
                        "yaxis": {"color": "white", "gridcolor": "#444"},
                        "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
                    }
                }

                # Обновляем info о записях (из Business long)
                count = len(dff_out_long)
                min_date = dff_out_long["DateTime"].min()
                max_date = dff_out_long["DateTime"].max()
                data_info = (
                    f"Количество заполненных записей из бизнеса: {count}. "
                    f"Первая дата: {min_date}. "
                    f"Последняя дата: {max_date}."
                )
            else:
                data_info = "Нет заполненных данных из Business"
        except:
            fig_out_long = {
                "data": [],
                "layout": {
                    "title": {"text": "Ошибка чтения Business CSV", "font": {"color": "white"}},
                    "paper_bgcolor": "#1A2138",
                    "plot_bgcolor": "#202946",
                    "font": {"color": "white"},
                    "xaxis": {"color": "white", "gridcolor": "#444"},
                    "yaxis": {"color": "white", "gridcolor": "#444"},
                    "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
                }
            }
    else:
        fig_out_long = {
            "data": [],
            "layout": {
                "title": {"text": "Нет файла Business long", "font": {"color": "white"}},
                "paper_bgcolor": "#1A2138",
                "plot_bgcolor": "#202946",
                "font": {"color": "white"},
                "xaxis": {"color": "white", "gridcolor": "#444"},
                "yaxis": {"color": "white", "gridcolor": "#444"},
                "margin": {"l": 50, "r": 20, "t": 40, "b": 30}
            }
        }
        data_info = ""

    # 8) Таблица out: читаем из Business/data_out_<true_port>.csv
    if os.path.exists(out_path):
        try:
            global df_out, df_input

            # Перечитываем, если обновился файл
            if (os.path.getmtime(out_path) >= os.path.getmtime(input_path)) or (df_out is None) or (df_input is None):
                df_out = pd.read_csv(out_path)
                df_input = pd.read_csv(input_path)

            # Фильтруем по дате, если нужно
            dff_out = df_out.copy()
            dff_input = df_input.copy()
            if start_date:
                dff_out = dff_out[dff_out["DateTime"] >= start_date]
                dff_input = dff_input[dff_input["DateTime"] >= start_date]
            if end_date:
                dff_out = dff_out[dff_out["DateTime"] <= end_date]
                dff_input = dff_input[dff_input["DateTime"] <= end_date]

            # Формируем data для таблицы
            out_table_data = []
            if feature in dff_out.columns:
                for idx, row in dff_out.iterrows():
                    out_table_data.append({
                        "DateTime": row["DateTime"],
                        "input": dff_input.iloc[idx][feature] if feature in dff_input.columns else "",
                        "value": row[feature]
                    })
            else:
                cols_out_simple = [c for c in dff_out.columns if c != "DateTime"]
                if cols_out_simple:
                    col0 = cols_out_simple[0]
                    for idx, row in dff_out.iterrows():
                        out_table_data.append({
                            "DateTime": row["DateTime"],
                            "input": dff_input.iloc[idx][col0] if col0 in dff_input.columns else "",
                            "value": row[col0]
                        })
        except:
            out_table_data = []
    else:
        out_table_data = []

   # 1) Считаем только последнюю строчку из CSV (если он есть)
    current_metrics = None
    metrics_file_columns = []
    if os.path.exists(metrics_path):
        try:
            dfm = pd.read_csv(metrics_path)
            if not dfm.empty:
                # берем последнюю строку как текущую метрику
                current_metrics = dfm.iloc[-1].to_dict()
                # колонки для таблицы берем из CSV (чтобы заголовки совпали)
                metrics_file_columns = [{"name": c, "id": c} for c in dfm.columns]
        except:
            pass

    # 2) Накопление истории в metrics_history (из dcc.Store)
    if not metrics_history:
        metrics_history = []
    # если пришла новая метрика, и она не дублирует последнюю в истории — добавляем
    if current_metrics and (not metrics_history or metrics_history[-1] != current_metrics):
        metrics_history.append(current_metrics)

    # 3) Собираем data для таблицы как всю накопленную историю
    metrics_file_data = metrics_history

    # 4) Отдельно собираем metrics_info (последняя строка для блока «Метрика работы модели»)
    metrics_info = ""
    if current_metrics:
        parts = [f"{k} = {v}" for k, v in current_metrics.items()]
        metrics_info = ", ".join(parts)

    # 11) Статус (оставляем пустым, если всё успешно)
    status = ""

    return (
        fig_raw,
        fig_filled,
        fig_out_long,
        metrics_info,
        data_info,
        status,
        out_table_data,
        metrics_file_columns,
        metrics_file_data,
        metrics_history,  
    )


# ----------------------
#  Запуск приложения
# ----------------------

if __name__ == "__main__":
    print("Запуск Dash-GUI (Polling-CSV)")
    app.run(debug=True, host="0.0.0.0", port=8050)
