import asyncio
from datetime import datetime, timedelta
import html
import logging
import os
import re
import threading

zoneinfo_available = True
try:
  from zoneinfo import ZoneInfo
except ImportError:
  zoneinfo_available = False

from flask import Flask
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configurar logs para ver errores detallados en Render
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==========================================
# 1. SERVIDOR WEB PARA EL PLAN GRATUITO DE RENDER
# ==========================================
app = Flask(__name__)


@app.route("/")
def home():
  return "¡El bot de apuestas @ApuestasCrisCol_bot está activo!"


def run_web():
  port = int(os.getenv("PORT", "10000"))
  app.run(host="0.0.0.0", port=port)


# ==========================================
# 2. LÓGICA DEL BOT: COMBINACIONES DE LA RED Y HORA COLOMBIA
# ==========================================
TOKEN = os.getenv(
    "TELEGRAM_TOKEN", "9077971398:AAHazVQzDFwfrkciKH3hDyB3wBJ8mfVeRY8"
)
ODDS_API_KEY = os.getenv(
    "ODDS_API_KEY", "d242634955bdd7ea26e6781fe19d3753"
)
TIPSTRR_LEAST_EXPECTED_URL = "https://tipstrr.com/tipster/the-least-expected"

# Ligas adicionales de Colombia y Suramérica para asegurar cobertura sin excepción
LIGAS_SURAMERICA_COLOMBIA = [
    "soccer_colombia_primera_a",
    "soccer_conmebol_copa_libertadores",
    "soccer_conmebol_copa_sudamericana",
    "soccer_brazil_campeonato",
    "soccer_brazil_serie_b",
    "soccer_argentina_primera_division",
    "soccer_chile_campeonato",
    "soccer_peru_liga_1",
    "soccer_ecuador_serie_a",
    "soccer_uruguay_primera_division",
    "soccer_paraguay_division_profesional",
    "soccer_venezuela_primera_division",
    "soccer_bolivia_division_profesional",
]


def obtener_stats_least_expected():
  """Consulta el perfil público de The Least Expected en Tipstrr sin dependencias extra."""
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      ),
      "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
  }
  try:
    resp = requests.get(TIPSTRR_LEAST_EXPECTED_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    raw_html = re.sub(
        r"<(script|style)[^>]*>.*?</\1>", " ", resp.text, flags=re.S | re.I
    )
    sin_tags = re.sub(r"<[^>]+>", " ", raw_html)
    texto = " ".join(html.unescape(sin_tags).split())

    roi_match = re.search(
        r"\bROI\b[:\s]+([+-]?\d+(?:\.\d+)?%)", texto, re.IGNORECASE
    )
    profit_match = re.search(
        r"\b(?:Profit|Beneficio)\b[:\s]+([+-]?[£$€]?\d+(?:,\d{3})*(?:\.\d+)?)",
        texto,
        re.IGNORECASE,
    )
    win_match = re.search(
        r"\b(?:Win Rate|Strike Rate|Acierto)\b[:\s]+(\d+(?:\.\d+)?%)",
        texto,
        re.IGNORECASE,
    )

    picks = []
    for bloque in re.split(r"(?<=[.!?])\s+|\s{2,}", texto):
      linea = bloque.strip()
      if (
          20 <= len(linea) <= 140
          and (" vs " in linea.lower() or "@" in linea.lower())
          and not any(
              ruido in linea.lower()
              for ruido in ["cookie", "privacy", "terms", "sign up", "log in"]
          )
      ):
        picks.append(linea)
      if len(picks) >= 5:
        break

    return {
        "disponible": True,
        "roi": roi_match.group(1) if roi_match else "Ver perfil en Tipstrr",
        "beneficio": (
            profit_match.group(1) if profit_match else "Ver perfil en Tipstrr"
        ),
        "acierto": win_match.group(1) if win_match else "Ver perfil en Tipstrr",
        "picks": picks,
        "url": TIPSTRR_LEAST_EXPECTED_URL,
    }
  except Exception as e:
    logger.error(f"Error consultando The Least Expected en Tipstrr: {e}")
    return {
        "disponible": False,
        "error": str(e),
        "url": TIPSTRR_LEAST_EXPECTED_URL,
    }


def _obtener_partidos_todas_las_ligas():
  """Consulta todos los partidos de fútbol disponibles, incluyendo Colombia y Suramérica."""
  eventos_combinados = []

  # 1. Consulta general de fútbol (todas las regiones)
  url_general = (
      f"https://api.the-odds-api.com/v4/sports/soccer/odds/"
      f"?apiKey={ODDS_API_KEY}&regions=eu,uk,us,au&markets=h2h&oddsFormat=decimal"
  )
  resp_general = requests.get(url_general, timeout=20)
  data_general = resp_general.json()

  if isinstance(data_general, dict) and "message" in data_general:
    raise RuntimeError(data_general["message"])

  if isinstance(data_general, list):
    eventos_combinados.extend(data_general)

  # 2. Consultas específicas por ligas de Colombia y Suramérica para no omitir ninguna
  for sport_key in LIGAS_SURAMERICA_COLOMBIA:
    url_liga = (
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        f"?apiKey={ODDS_API_KEY}&regions=eu,uk,us,au&markets=h2h&oddsFormat=decimal"
    )
    try:
      resp_liga = requests.get(url_liga, timeout=12)
      data_liga = resp_liga.json()
      if isinstance(data_liga, list) and data_liga:
        eventos_combinados.extend(data_liga)
    except Exception as e:
      logger.warning(f"No se pudo consultar la liga {sport_key}: {e}")

  return eventos_combinados


def _extraer_cuotas_red(partido: dict) -> dict:
  """Extrae las cuotas reales de mercado (h2h) reportadas por la red."""
  home_team = partido.get("home_team", "Local").strip()
  away_team = partido.get("away_team", "Visitante").strip()

  cuota_local = None
  cuota_visitante = None
  cuota_empate = None
  casa_ref = None

  for bm in partido.get("bookmakers", []):
    for market in bm.get("markets", []):
      if market.get("key") == "h2h":
        for outcome in market.get("outcomes", []):
          name = outcome.get("name", "").strip().lower()
          price = outcome.get("price")
          if price is None:
            continue
          price_val = float(price)
          if name == home_team.lower():
            cuota_local = price_val
          elif name == away_team.lower():
            cuota_visitante = price_val
          elif name == "draw":
            cuota_empate = price_val
        casa_ref = bm.get("title") or bm.get("key")
        break
    if cuota_local is not None or cuota_visitante is not None:
      break

  candidatos = []
  if cuota_local and cuota_local > 1.0:
    candidatos.append((f"Gana {home_team}", cuota_local))
  if cuota_empate and cuota_empate > 1.0:
    candidatos.append(("Empate", cuota_empate))
  if cuota_visitante and cuota_visitante > 1.0:
    candidatos.append((f"Gana {away_team}", cuota_visitante))

  if candidatos:
    seleccion_top, cuota_top = min(candidatos, key=lambda x: x[1])
    efectividad_red = int(round(min(max((1.0 / cuota_top) * 100, 15), 92)))
  else:
    seleccion_top, cuota_top = "Sin cuota h2h", 0.0
    efectividad_red = 0

  return {
      "cuota_local": cuota_local,
      "cuota_visitante": cuota_visitante,
      "cuota_empate": cuota_empate,
      "casa_ref": casa_ref or "Red",
      "seleccion_top": seleccion_top,
      "cuota_top": cuota_top,
      "efectividad_red": efectividad_red,
  }


def _construir_combinadas_de_red(
    partidos_red: list, least_exp: dict
) -> list:
  """Arma combinadas a partir de las cuotas reales de red y registros públicos de Tipstrr."""
  validos = [p for p in partidos_red if p["cuotas"]["cuota_top"] > 1.0]
  validos.sort(key=lambda x: x["cuotas"]["cuota_top"])

  combinadas = []
  for tam in (2, 3):
    grupo = validos[:tam]
    if len(grupo) < tam:
      continue
    legs = []
    cuota_comb = 1.0
    for item in grupo:
      c_info = item["cuotas"]
      legs.append(
          f"{item['home_team']} vs {item['away_team']} ->"
          f" {c_info['seleccion_top']} (`@{c_info['cuota_top']}`)"
      )
      cuota_comb *= c_info["cuota_top"]
    cuota_comb = round(cuota_comb, 2)
    prob_comb = int(round(min(max((1.0 / max(cuota_comb, 1.05)) * 100, 10), 85)))
    combinadas.append({
        "titulo": f"Combinada de Red (x{len(grupo)} - Cuotas Reales)",
        "legs": legs,
        "cuota_total": f"x{cuota_comb}",
        "efectividad": f"{prob_comb}%",
    })

  if least_exp.get("disponible") and least_exp.get("picks"):
    combinadas.append({
        "titulo": "Picks Públicos de Red (The Least Expected - Tipstrr)",
        "legs": least_exp["picks"][:3],
        "cuota_total": "Ver en Tipstrr",
        "efectividad": least_exp.get("acierto", "Ver perfil en Tipstrr"),
    })

  return combinadas


def _dividir_texto_seguro(texto: str, limite_absoluto: int = 3950) -> list:
  """Garantiza que ningún mensaje supere el límite de caracteres de Telegram."""
  if len(texto) <= limite_absoluto:
    return [texto]
  trozos = []
  inicio = 0
  while inicio < len(texto):
    fin = min(inicio + limite_absoluto, len(texto))
    if fin < len(texto):
      salto = texto.rfind("\n", inicio, fin)
      if salto > inicio + 500:
        fin = salto + 1
    trozos.append(texto[inicio:fin])
    inicio = fin
  return trozos


def _armar_mensajes_telegram(
    partidos_evaluados: list,
    combinadas_red: list,
    least_exp: dict,
    total_partidos: int,
    max_chars: int = 3850,
) -> list:
  """Divide todos los partidos en los mensajes de Telegram necesarios de forma compacta y segura."""
  bloques_partidos = []
  bloque_actual = []
  chars_actuales = 0

  for idx, item in enumerate(partidos_evaluados, 1):
    c_info = item["cuotas"]
    ficha = (
        f"⚽ *{idx}. {item['home_team']} vs {item['away_team']}*\n"
        f"🏆 {item['liga_sport']} | 🇨🇴 `{item['hora_col']}`\n"
        f"📊 1X2: `{c_info['cuota_local']}` / `{c_info['cuota_empate']}` /"
        f" `{c_info['cuota_visitante']}` ({c_info['casa_ref']})\n"
        f"🎯 Red: {c_info['seleccion_top']} (`@{c_info['cuota_top']}`)"
        f" | Prob: `{c_info['efectividad_red']}%`\n\n"
    )

    if bloque_actual and (chars_actuales + len(ficha) > max_chars):
      bloques_partidos.append(bloque_actual)
      bloque_actual = [ficha]
      chars_actuales = len(ficha)
    else:
      bloque_actual.append(ficha)
      chars_actuales += len(ficha)

  if bloque_actual:
    bloques_partidos.append(bloque_actual)

  pie_final = ""
  if combinadas_red:
    pie_final += "🌐 **COMBINACIONES PROPORCIONADAS POR LA RED:**\n"
    for c_red in combinadas_red:
      pie_final += (
          f"• *{c_red['titulo']}* — Prob./Ref.: `{c_red['efectividad']}`"
          f" | Cuota: `{c_red['cuota_total']}`\n"
      )
      for leg in c_red["legs"]:
        pie_final += f"  ◦ {leg}\n"

  pie_final += (
      "\n_💡 Red (The Odds API / Tipstrr) | 1h+ anticipación | "
      f"Partidos analizados: {total_partidos}_"
  )
  if least_exp.get("disponible"):
    pie_final += (
        "\n🏆 **The Least Expected:** "
        f"ROI `{least_exp['roi']}` | Beneficio"
        f" `{least_exp['beneficio']}` | Acierto `{least_exp['acierto']}`"
    )

  if bloques_partidos:
    ultimo_chars = sum(len(x) for x in bloques_partidos[-1])
    if ultimo_chars + len(pie_final) > max_chars:
      bloques_partidos.append([pie_final])
    else:
      bloques_partidos[-1].append(pie_final)
  else:
    bloques_partidos.append([pie_final])

  mensajes_borrador = []
  for partes in bloques_partidos:
    mensajes_borrador.extend(_dividir_texto_seguro("".join(partes)))

  total_mensajes = len(mensajes_borrador)
  mensajes_finales = []
  for num_msg, cuerpo in enumerate(mensajes_borrador, 1):
    encabezado = (
        f"🌐 **CARTELERA Y CUOTAS DE RED ({num_msg}/{total_mensajes})** ⚽\n\n"
    )
    msg_completo = encabezado + cuerpo
    mensajes_finales.extend(_dividir_texto_seguro(msg_completo))

  return mensajes_finales


async def least_expected_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "📊 Consultando estadísticas y pronósticos públicos de **The Least Expected** (Tipstrr)...",
      parse_mode="Markdown",
  )
  datos = await asyncio.to_thread(obtener_stats_least_expected)
  if not datos["disponible"]:
    await update.message.reply_text(
        f"⚠️ No se pudo leer el perfil público de **The Least Expected** en este momento.\n"
        f"🔗 Consulta directa: {datos['url']}",
        parse_mode="Markdown",
    )
    return

  msg = (
      "🏆 **The Least Expected (Tipstrr - Fútbol)**\n"
      f"📈 **ROI:** `{datos['roi']}`\n"
      f"💰 **Beneficio:** `{datos['beneficio']}`\n"
      f"🎯 **Acierto:** `{datos['acierto']}`\n"
  )
  if datos["picks"]:
    msg += "\n📌 **Picks / registros visibles:**\n"
    for p in datos["picks"]:
      msg += f"• {p}\n"
  msg += f"\n🔗 Fuente: {datos['url']}"

  await update.message.reply_text(msg, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "¡Hola! Bienvenido al asistente **@ApuestasCrisCol_bot** ⚽🔥\n\n"
      "Te ofrezco datos y combinaciones proporcionadas por la red:\n"
      "📌 Usa **/combinadas** para ver **todos los partidos de todas las ligas** (incluyendo Colombia y Suramérica) con al menos **1 hora** de anticipación, cuotas reales de red y combinaciones de red.\n"
      "📌 Usa **/leastexpected** para ver los datos y resultados públicos de **The Least Expected**."
  )


async def combinadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "🔄 Escaneando todos los partidos de todas las ligas (incluyendo Colombia y Suramérica) con 1 hora de anticipación..."
  )

  try:
    data = await asyncio.to_thread(_obtener_partidos_todas_las_ligas)

    if not isinstance(data, list) or len(data) == 0:
      await update.message.reply_text(
          "⚠️ No se encontraron partidos disponibles en este momento en la API de cuotas. Inténtalo más tarde."
      )
      return

    if zoneinfo_available:
      try:
        colombia_tz = ZoneInfo("America/Bogota")
        ahora_col = datetime.now(colombia_tz)
      except Exception:
        ahora_col = datetime.now() - timedelta(hours=5)
    else:
      ahora_col = datetime.utcnow() - timedelta(hours=5)

    # Filtro estricto de 1 hora (60 minutos) de anticipación
    limite_anticipacion = ahora_col + timedelta(hours=1)

    partidos_validos = []
    vistos = set()

    for partido in data:
      h = partido.get("home_team", "").strip()
      a = partido.get("away_team", "").strip()
      commence_time_str = partido.get("commence_time", "")
      clave = f"{h}-{a}-{commence_time_str}"

      try:
        limpio = commence_time_str.replace("Z", "+00:00")
        utc_dt = datetime.fromisoformat(limpio)

        if zoneinfo_available:
          partido_col_dt = utc_dt.astimezone(ZoneInfo("America/Bogota"))
        else:
          partido_col_dt = utc_dt - timedelta(hours=5)

        if partido_col_dt < limite_anticipacion:
          continue

      except Exception:
        continue

      if clave not in vistos:
        vistos.add(clave)
        partidos_validos.append((partido, partido_col_dt))

    # Ordenar cronológicamente por hora de inicio en Colombia
    partidos_validos.sort(key=lambda x: x[1])
    total_partidos = len(partidos_validos)

    if total_partidos == 0:
      await update.message.reply_text(
          "⚠️ No hay partidos disponibles con al menos 1 hora de anticipación en este momento."
      )
      return

    partidos_evaluados = []
    for partido, partido_col_dt in partidos_validos:
      home_team = partido.get("home_team", "Local")
      away_team = partido.get("away_team", "Visitante")
      liga_sport = partido.get("sport_title", "Fútbol Internacional")
      hora_col = partido_col_dt.strftime("%d/%m/%Y - %I:%M %p")

      cuotas = _extraer_cuotas_red(partido)
      partidos_evaluados.append({
          "home_team": home_team,
          "away_team": away_team,
          "liga_sport": liga_sport,
          "hora_col": hora_col,
          "cuotas": cuotas,
      })

    least_exp = await asyncio.to_thread(obtener_stats_least_expected)
    combinadas_red = _construir_combinadas_de_red(partidos_evaluados, least_exp)

    mensajes = _armar_mensajes_telegram(
        partidos_evaluados=partidos_evaluados,
        combinadas_red=combinadas_red,
        least_exp=least_exp,
        total_partidos=total_partidos,
    )

    for mensaje in mensajes:
      await update.message.reply_text(mensaje, parse_mode="Markdown")
      await asyncio.sleep(0.7)

  except Exception as e:
    logger.error(f"Error al consultar The Odds API: {e}")
    await update.message.reply_text(
        "⚠️ Ocurrió un error al conectar con el servidor global de cuotas. "
        "Verifica tu conexión o inténtalo en unos segundos."
    )


async def error_handler(object, context: ContextTypes.DEFAULT_TYPE):
  logger.error("Excepción al manejar una actualización:", exc_info=context.error)


def run_bot():
  print(
      "Iniciando el bot con todas las ligas (incluyendo Colombia y Suramérica) y filtro de 1 hora..."
  )
  application = ApplicationBuilder().token(TOKEN).build()

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CommandHandler("combinadas", combinadas))
  application.add_handler(CommandHandler("leastexpected", least_expected_cmd))
  application.add_error_handler(error_handler)

  application.run_polling()


if __name__ == "__main__":
  web_thread = threading.Thread(target=run_web)
  web_thread.daemon = True
  web_thread.start()

  run_bot()
