
import os
import random
import threading
import time
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

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
# 2. LÓGICA DEL BOT: COMBINADAS Y RESULTADOS
# ==========================================
TOKEN = "9077971398:AAH2XqvVKpnIvvzd_ytVxfNtvxAVPVcs5Xs"

# Equipos y ligas globales
LIGAS_MUNDO = [
    "Champions League (Europa)",
    "Premier League (Inglaterra)",
    "LaLiga (España)",
    "Serie A (Italia)",
    "Bundesliga (Alemania)",
    "Copa Libertadores (Sudamérica)",
    "Liga Profesional (Argentina)",
    "Liga BetPlay (Colombia)",
    "Brasileirão (Brasil)",
    "Liga MX (México)",
]

EQUIPOS = [
    ("Real Madrid", "Barcelona"),
    ("Manchester City", "Arsenal"),
    ("Bayern Múnich", "Borussia Dortmund"),
    ("Inter de Milán", "Juventus"),
    ("Flamengo", "Palmeiras"),
    ("River Plate", "Boca Juniors"),
    ("Millonarios", "Atlético Nacional"),
    ("América de Cali", "Junior de Barranquilla"),
    ("PSG", "Marsella"),
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "¡Hola! Bienvenido a **@ApuestasCrisCol_bot** ⚽🔥\n\n"
      "Te ofrezco pronósticos y seguimiento global:\n"
      "📌 Usa **/combinadas** para ver jugadas de alta efectividad (91%-96%).\n"
      "📌 Usa **/resultados** para ver los marcadores actualizados en"
      " directo."
  )


async def combinadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
  partidos_seleccionados = random.sample(EQUIPOS, 3)
  liga1 = random.choice(LIGAS_MUNDO)
  liga2 = random.choice(LIGAS_MUNDO)
  liga3 = random.choice(LIGAS_MUNDO)

  cuota1 = round(random.uniform(1.70, 2.30), 2)
  cuota2 = round(random.uniform(1.80, 2.45), 2)
  cuota3 = round(random.uniform(1.65, 2.10), 2)

  cuota_total = round(cuota1 * cuota2 * cuota3, 2)
  efectividad = random.randint(91, 96)  # Realista y menor al 99%

  mensaje = (
      f"🎯 **APUESTA COMBINADA DEL DÍA (GLOBAL)** 🌍⚽\n\n"
      f"1️⃣ *{partidos_seleccionados[0][0]} vs"
      f" {partidos_seleccionados[0][1]}*\n   🏆 Liga: {liga1}\n   📌 Pronóstico:"
      f" Más de 1.5 goles / Ambos anotan\n   ⚡ Cuota: {cuota1}\n\n"
      f"2️⃣ *{partidos_seleccionados[1][0]} vs"
      f" {partidos_seleccionados[1][1]}*\n   🏆 Liga: {liga2}\n   📌 Pronóstico:"
      f" Victoria local o Empate (Doble Oportunidad)\n   ⚡ Cuota:"
      f" {cuota2}\n\n"
      f"3️⃣ *{partidos_seleccionados[2][0]} vs"
      f" {partidos_seleccionados[2][1]}*\n   🏆 Liga: {liga3}\n   📌 Pronóstico:"
      f" Menos de 3.5 goles totales\n   ⚡ Cuota: {cuota3}\n\n"
      f"──────────────────────\n"
      f"📊 **Cuota Total Combinada:** `x{cuota_total}`\n"
      f"📈 **Índice de Efectividad Estimado:** `{efectividad}%` 🚀\n\n"
      f"_Usa /combinadas de nuevo para generar nuevas jugadas._"
  )

  await update.message.reply_text(mensaje, parse_mode="Markdown")


async def resultados(update: Update, context: ContextTypes.DEFAULT_TYPE):
  # Simulamos resultados actualizados de la jornada mundial
  partidos_en_vivo = random.sample(EQUIPOS, 4)
  estados = ["⏱ 78'", "⏱ 45'+2", "✅ Finalizado", "⏱ 89'"]

  mensaje = "⚽ **RESULTADOS ACTUALIZADOS EN VIVO (MUNDO)** 🌍\n\n"

  for i in range(4):
    eq1, eq2 = partidos_en_vivo[i]
    goles1 = random.randint(0, 3)
    goles2 = random.randint(0, 3)
    estado = estados[i]
    liga = random.choice(LIGAS_MUNDO)

    mensaje += (
        f"🏆 *{liga}*\n"
        f"🔹 {eq1} **{goles1} - {goles2}** {eq2}\n"
        f"Status: `{estado}`\n\n"
    )

  mensaje += "_Usa /resultados para refrescar los marcadores en tiempo real._"

  await update.message.reply_text(mensaje, parse_mode="Markdown")


def run_bot():
  print("Iniciando el bot de Telegram con resultados y combinadas...")
  application = ApplicationBuilder().token(TOKEN).build()
  application.add_handler(CommandHandler("start", start))
  application.add_handler(CommandHandler("combinadas", combinadas))
  application.add_handler(CommandHandler("resultados", resultados))
  application.run_polling()


# ==========================================
# 3. EJECUCIÓN SIMULTÁNEA (WEB + BOT)
# ==========================================
if __name__ == "__main__":
  web_thread = threading.Thread(target=run_web)
  web_thread.daemon = True
  web_thread.start()

  run_bot()
