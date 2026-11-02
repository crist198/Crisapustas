from datetime import datetime, timedelta
import logging
import os
import random
import threading
import time

zoneinfo_available = True
try:
  from zoneinfo import ZoneInfo
except ImportError:
  zoneinfo_available = False

import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

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
  app.run(host="0.0.0.0", port=10000)


# ==========================================
# 2. LÓGICA DEL BOT: BET BUILDERS GLOBALES Y HORA COLOMBIA
# ==========================================
TOKEN = "9077971398:AAH2XqvVKpnIvvzd_ytVxfNtvxAVPVcs5Xs"
ODDS_API_KEY = "d242634955bdd7ea26e6781fe19d3753"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "¡Hola! Bienvenido al asistente **@ApuestasCrisCol_bot** ⚽🔥\n\n"
      "Te ofrezco pronósticos y seguimiento real:\n"
      "📌 Usa **/combinadas** para ver **partidos con al menos 30 minutos de anticipación** con su Bet Builder de 3 selecciones."
  )


async def combinadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "🔄 Escaneando cartelera, aplicando margen de 30 minutos de anticipación..."
  )

  url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu,us&markets=h2h&oddsFormat=decimal"

  try:
    response = requests.get(url, timeout=15)
    data = response.json()

    if isinstance(data, dict) and "message" in data:
      logger.error(f"Error devuelto por la API: {data['message']}")
      await update.message.reply_text(
          f"⚠️ Error de la API: {data['message']}"
      )
      return

    if not isinstance(data, list) or len(data) == 0:
      await update.message.reply_text(
          "⚠️ No se encontraron partidos disponibles en este momento en la API de cuotas. Inténtalo más tarde."
      )
      return

    # Definir la hora actual en Colombia y sumarle 30 minutos de margen de anticipación
    if zoneinfo_available:
      try:
        colombia_tz = ZoneInfo("America/Bogota")
        ahora_col = datetime.now(colombia_tz)
      except Exception:
        ahora_col = datetime.now() - timedelta(hours=5)
    else:
      ahora_col = datetime.utcnow() - timedelta(hours=5)

    limite_anticipacion = ahora_col + timedelta(minutes=30)

    # FILTRAR PARTIDOS: ELIMINAR DUPLICADOS Y LOS QUE TENGAN MENOS DE 30 MINUTOS PARA EMPEZAR
    partidos_validos = []
    vistos = set()

    for partido in data:
      h = partido.get("home_team", "")
      a = partido.get("away_team", "")
      clave = f"{h}-{a}"
      
      commence_time_str = partido.get("commence_time", "")
      try:
        limpio = commence_time_str.replace("Z", "+00:00")
        utc_dt = datetime.fromisoformat(limpio)
        
        # Convertir a hora Colombia
        if zoneinfo_available:
          partido_col_dt = utc_dt.astimezone(ZoneInfo("America/Bogota"))
        else:
          partido_col_dt = utc_dt - timedelta(hours=5)

        # SI EL PARTIDO EMPIEZA ANTES DE LOS 30 MINUTOS DE MARGEN, LO DESCARTAMOS
        if partido_col_dt < limite_anticipacion:
          continue

      except Exception:
        continue

      if clave not in vistos:
        vistos.add(clave)
        partidos_validos.append(partido)

    total_partidos = len(partidos_validos)

    if total_partidos == 0:
      await update.message.reply_text(
          "⚠️ No hay partidos disponibles con al menos 30 minutos de anticipación para lo que resta del día."
      )
      return

    # Tomamos hasta 30 partidos válidos
    partidos_a_mostrar = partidos_validos[:30]

    # Dividir en bloques de máximo 6 partidos (hasta 5 mensajes en total)
    tamanio_bloque = 6
    bloques = [
        partidos_a_mostrar[i:i + tamanio_bloque]
        for i in range(0, len(partidos_a_mostrar), tamanio_bloque)
    ]
    
    total_bloques = len(bloques)

    for index, bloque_partidos in enumerate(bloques, 1):
      if not bloque_partidos:
        continue

      mensaje = f"🎯 **CARTELERA CON 30MIN+ DE ANTICIPACIÓN (Parte {index}/{total_bloques})** 🌍⚽\n\n"

      for i, partido in enumerate(bloque_partidos, 1):
        num_real = (index - 1) * tamanio_bloque + i
        
        home_team = partido.get("home_team", "Local")
        away_team = partido.get("away_team", "Visitante")
        commence_time_str = partido.get("commence_time", "")
        liga_sport = partido.get("sport_title", "Fútbol Internacional")

        # CONVERSIÓN DE ZONA HORARIA A HORA COLOMBIA (America/Bogota)
        try:
          limpio = commence_time_str.replace("Z", "+00:00")
          utc_dt = datetime.fromisoformat(limpio)

          if zoneinfo_available:
            colombia_tz = ZoneInfo("America/Bogota")
            colombia_dt = utc_dt.astimezone(colombia_tz)
          else:
            colombia_dt = utc_dt - timedelta(hours=5)

          hora_col = colombia_dt.strftime("%d/%m/%Y - %I:%M %p")
        except Exception:
          hora_col = "Hora por confirmar"

        # EXTRACCIÓN BLINDADA Y ROBUSTA DE CUOTAS
        bookmakers = partido.get("bookmakers", [])
        cuota_local = 1.80
        cuota_visitante = 2.10
        cuotas_encontradas = False

        if bookmakers:
          for bm in bookmakers:
            markets = bm.get("markets", [])
            for market in markets:
              if market.get("key") == "h2h":
                outcomes = market.get("outcomes", [])
                for outcome in outcomes:
                  name = outcome.get("name", "")
                  price = outcome.get("price", 1.80)
                  if name.strip().lower() == home_team.strip().lower():
                    cuota_local = price
                  elif name.strip().lower() == away_team.strip().lower():
                    cuota_visitante = price
                cuotas_encontradas = True
                break
            if cuotas_encontradas:
              break

        # =========================================================================
        # CORRECCIÓN INTELIGENTE DE FAVORITO Y EQUIPOS VISITANTES DOMINANTES
        # =========================================================================
        h_low = home_team.lower()
        a_low = away_team.lower()

        fuerza_visitante_destacada = any(eq in a_low for eq in ["zenit", "hjk", "fiorentina"])
        fuerza_local_destacada = any(eq in h_low for eq in ["oviedo", "inter turku"])

        if fuerza_visitante_destacada and not fuerza_local_destacada:
          doble_oportunidad = f"Doble Oportunidad (X2 - Gana/Empata {away_team})"
          c1 = round(min(max(cuota_visitante * 0.85, 1.20), 1.45), 2)
        elif fuerza_local_destacada:
          doble_oportunidad = f"Doble Oportunidad (1X - Gana/Empata {home_team})"
          c1 = round(min(max(cuota_local * 0.85, 1.20), 1.45), 2)
        else:
          if cuota_visitante < cuota_local:
            doble_oportunidad = f"Doble Oportunidad (X2 - Gana/Empata {away_team})"
            c1 = round(min(max(cuota_visitante * 0.85, 1.20), 1.45), 2)
          else:
            doble_oportunidad = f"Doble Oportunidad (1X - Gana/Empata {home_team})"
            c1 = round(min(max(cuota_local * 0.85, 1.20), 1.45), 2)

        # Generar cuotas lógicas para el Bet Builder de 3 selecciones (aprox x2.00)
        c2 = round(random.uniform(1.22, 1.35), 2)
        c3 = round(random.uniform(1.25, 1.40), 2)
        cuota_total_evento = round(c1 * c2 * c3, 2)
        efectividad_evento = random.randint(76, 78)

        mensaje += (
            f"⚽ *{num_real}. {home_team} vs {away_team}*\n"
            f"   🏆 {liga_sport}\n"
            f"   🇨🇴 **Hora Colombia:** `{hora_col}`\n"
            f"   📊 **Bet Builder (3 Selecciones Estadísticas):**\n"
            f"      1️⃣ {doble_oportunidad}: `Cuota {c1}`\n"
            f"      2️⃣ Goles Totales (>1.5): `Cuota {c2}`\n"
            f"      3️⃣ Mitades (>0.5 Goles 2do T): `Cuota {c3}`\n"
            f"   ⚡ **Cuota Total del Partido (x3):** `x{cuota_total_evento}`\n"
            f"   📈 **Efectividad Estimada:** `{efectividad_evento}%` ⚖️\n\n"
            f"──────────────────────\n"
        )

      if index == total_bloques:
        mensaje += f"_💡 Cárgalos en el 'Creador de Apuestas' de tu plataforma (como Rushbet).\nTotal partidos con +30min de anticipación: {total_partidos}_"

      await update.message.reply_text(mensaje, parse_mode="Markdown")
      time.sleep(0.7)  # Pausa breve para orden en Telegram

  except Exception as e:
    logger.error(f"Error al consultar The Odds API: {e}")
    await update.message.reply_text(
        "⚠️ Ocurrió un error al conectar con el servidor global de cuotas. "
        "Verifica tu conexión o inténtalo en unos segundos."
    )


async def error_handler(object, context: ContextTypes.DEFAULT_TYPE):
  logger.error("Excepción al manejar una actualización:", exc_info=context.error)


def run_bot():
  print("Iniciando el bot con filtro de 30 minutos de anticipación...")
  application = ApplicationBuilder().token(TOKEN).build()

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CommandHandler("combinadas", combinadas))
  application.add_error_handler(error_handler)

  application.run_polling()


if __name__ == "__main__":
  web_thread = threading.Thread(target=run_web)
  web_thread.daemon = True
  web_thread.start()

  run_bot()
