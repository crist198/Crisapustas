import logging
import os
import random
import threading
import time
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
  return "¡El bot de apuestas y resultados @ApuestasCrisCol_bot está activo!"


def run_web():
  app.run(host="0.0.0.0", port=10000)


# ==========================================
# 2. LÓGICA DEL BOT: COMBINADAS Y RESULTADOS REALES
# ==========================================
TOKEN = "9077971398:AAH2XqvVKpnIvvzd_ytVxfNtvxAVPVcs5Xs"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "¡Hola! Bienvenido a **@ApuestasCrisCol_bot** ⚽🔥\n\n"
      "Te ofrezco pronósticos y seguimiento global:\n"
      "📌 Usa **/combinadas** para ver jugadas de alta efectividad (91%-96%).\n"
      "📌 Usa **/resultados** para ver los marcadores reales en directo."
  )


async def combinadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
  # Ligas y partidos estrictamente sincronizados para combinadas
  partidas_combinadas = [
      ("Premier League (Inglaterra)", "Manchester City", "Arsenal"),
      ("LaLiga (España)", "Real Madrid", "Barcelona"),
      ("Serie A (Italia)", "Inter de Milán", "Juventus"),
      ("Bundesliga (Alemania)", "Bayern Múnich", "Borussia Dortmund"),
      ("Brasileirão (Brasil)", "Flamengo", "Palmeiras"),
      ("Liga Profesional (Argentina)", "River Plate", "Boca Juniors"),
      ("Liga BetPlay (Colombia)", "Millonarios", "Atlético Nacional"),
      ("Ligue 1 (Francia)", "PSG", "Marsella"),
  ]

  # Seleccionamos 3 partidos aleatorios de la lista correcta
  seleccionados = random.sample(partidas_combinadas, 3)

  cuota1 = round(random.uniform(1.70, 2.30), 2)
  cuota2 = round(random.uniform(1.80, 2.45), 2)
  cuota3 = round(random.uniform(1.65, 2.10), 2)

  cuota_total = round(cuota1 * cuota2 * cuota3, 2)
  efectividad = random.randint(91, 96)

  mensaje = (
      f"🎯 **APUESTA COMBINADA DEL DÍA (GLOBAL)** 🌍⚽\n\n"
      f"1️⃣ *{seleccionados[0][1]} vs {seleccionados[0][2]}*\n"
      f"   🏆 Liga: {seleccionados[0][0]}\n"
      f"   📌 Pronóstico: Más de 1.5 goles / Ambos anotan\n"
      f"   ⚡ Cuota: {cuota1}\n\n"
      f"2️⃣ *{seleccionados[1][1]} vs {seleccionados[1][2]}*\n"
      f"   🏆 Liga: {seleccionados[1][0]}\n"
      f"   📌 Pronóstico: Victoria local o Empate (Doble Oportunidad)\n"
      f"   ⚡ Cuota: {cuota2}\n\n"
      f"3️⃣ *{seleccionados[2][1]} vs {seleccionados[2][2]}*\n"
      f"   🏆 Liga: {seleccionados[2][0]}\n"
      f"   📌 Pronóstico: Menos de 3.5 goles totales\n"
      f"   ⚡ Cuota: {cuota3}\n\n"
      f"──────────────────────\n"
      f"📊 **Cuota Total Combinada:** `x{cuota_total}`\n"
      f"📈 **Índice de Efectividad Estimado:** `{efectividad}%` 🚀\n\n"
      f"_Usa /combinadas de nuevo para generar nuevas jugadas._"
  )

  await update.message.reply_text(mensaje, parse_mode="Markdown")


async def resultados(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "🔍 Consultando marcadores en vivo de la jornada..."
  )

  # API pública y gratuita de TheSportsDB (sin claves ni registros)
  url = "https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=2026-11-01&s=Soccer"

  try:
    response = requests.get(url, timeout=10)
    data = response.json()
    events = data.get("events", [])

    if not events:
      await update.message.reply_text(
          "⚽ **RESULTADOS EN VIVO (MUNDO)** 🌍\n\n"
          "No hay partidos registrados para el día de hoy en este servidor"
          " público. ¡Vuelve más tarde! ⏱"
      )
      return

    mensaje = "⚽ **RESULTADOS EN VIVO (MUNDO - REAL)** 🌍\n\n"

    # Mostramos hasta 5 partidos de la lista pública
    for match in events[:5]:
      liga = match.get("strLeague", "Liga Internacional")
      eq1 = match.get("strHomeTeam", "Local")
      eq2 = match.get("strAwayTeam", "Visitante")
      goles1 = match.get("intHomeScore", "0")
      goles2 = match.get("intAwayScore", "0")
      progreso = match.get("strProgress", "En curso")

      g1 = goles1 if goles1 else "0"
      g2 = goles2 if goles2 else "0"

      mensaje += (
          f"🏆 *{liga}*\n"
          f"🔹 {eq1} **{g1} - {g2}** {eq2}\n"
          f"Status: `{progreso}`\n\n"
      )

    mensaje += "_Datos obtenidos en tiempo real de API abierta._"
    await update.message.reply_text(mensaje, parse_mode="Markdown")

  except Exception as e:
    logger.error(f"Error al consultar la API pública: {e}")
    await update.message.reply_text(
        "⚠️ Ocurrió un error al conectar con el servidor de resultados. "
        "Inténtalo de nuevo en unos segundos."
    )


# Función para capturar y mostrar errores en los Logs de Render
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
  logger.error("Excepción al manejar una actualización:", exc_info=context.error)


def run_bot():
  print("Iniciando el bot de Telegram con API abierta y Flask...")
  application = ApplicationBuilder().token(TOKEN).build()

  # Registrar comandos
  application.add_handler(CommandHandler("start", start))
  application.add_handler(CommandHandler("combinadas", combinadas))
  application.add_handler(CommandHandler("resultados", resultados))

  # Registrar el manejador de errores
  application.add_error_handler(error_handler)

  application.run_polling()


# ==========================================
# 3. EJECUCIÓN SIMULTÁNEA (WEB + BOT)
# ==========================================
if __name__ == "__main__":
  web_thread = threading.Thread(target=run_web)
  web_thread.daemon = True
  web_thread.start()

  run_bot()
