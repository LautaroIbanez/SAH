import tkinter as tk
from tkinter import filedialog, messagebox
import fitz  # PyMuPDF
import re
from datetime import datetime
import pandas as pd

# --- Funciones auxiliares ---

def extraer_sueldos(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()

        lines = text.splitlines()

        # Mostrar log de líneas analizadas
        print("[Texto procesado para extracción de sueldos]:")
        for line in lines:
            print(line)

        # Buscar todas las líneas que contienen solo un número con formato sueldo
        monto_regex = re.compile(r'^\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$')
        valores = [match.group(1) for line in lines if (match := monto_regex.match(line))]

        if len(valores) < 2:
            print("[ERROR] No se encontraron suficientes montos claros para bruto/neto")
            return None, None

        valores_f = [float(v.replace('.', '').replace(',', '.')) for v in valores]

        # Sueldo neto: último valor
        sueldo_neto = valores_f[-1]

        # Sueldo bruto: el mayor entre los últimos 5 valores que superen 1.000.000
        candidatos = [v for v in valores_f[-6:] if v > 1_000_000]
        if not candidatos:
            print("[ERROR] No se detectó un valor alto para el sueldo bruto.")
            return None, None
        sueldo_bruto = max(candidatos)

        print(f"[BRUTO FINAL] Valor: {sueldo_bruto}")
        print(f"[NETO FINAL] Valor: {sueldo_neto}")

        return sueldo_bruto, sueldo_neto

    except Exception as e:
        print("Error al procesar PDF:", e)
        return None, None

def calcular_bloques_forzado(pdf_path):
    CODIGOS_BRUTO = {"20", "30", "40", "97", "103", "280", "281", "330", "350"}
    CODIGOS_DEDUCCIONES = {"7000", "7005", "7010", "8005"}

    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()

        lines = text.splitlines()

        # Mostrar log de líneas analizadas
        print("[Texto procesado para extracción de sueldos]:")
        for line in lines:
            print(line)

        bruto = 0.0
        deducciones = 0.0
        detectados = []

        i = 0
        while i < len(lines) - 2:
            linea_codigo = lines[i].strip()
            linea_valor = lines[i + 2].strip()

            # Extraer código desde primeros dígitos
            codigo = linea_codigo.split(" ")[0].strip()

            if codigo.isdigit() and re.match(r'^-?\d{1,3}(?:\.\d{3})*,\d{2}$', linea_valor):
                valor = float(linea_valor.replace('.', '').replace(',', '.'))

                tipo = ""
                if codigo in CODIGOS_BRUTO:
                    bruto += valor
                    tipo = "REM"
                elif codigo in CODIGOS_DEDUCCIONES:
                    deducciones += valor
                    tipo = "DED"

                if tipo:
                    detectados.append((codigo, valor, tipo, linea_codigo))

                i += 3
            else:
                i += 1

        neto = bruto - deducciones
        return round(bruto, 2), round(deducciones, 2), round(neto, 2), detectados
    
    except Exception as e:
        print("Error al procesar PDF:", e)
        return None, None


def calcular_cuota(monto, cuotas, tasa_anual):
    tasa_mensual = (tasa_anual / 100) / 12
    if tasa_mensual == 0:
        return monto / cuotas
    cuota = monto * (tasa_mensual * (1 + tasa_mensual)**cuotas) / ((1 + tasa_mensual)**cuotas - 1)
    return cuota

def generar_cuadro_amortizacion(monto, cuotas, tasa_anual):
    tasa_mensual = (tasa_anual / 100) / 12
    cuota_total = calcular_cuota(monto, cuotas, tasa_anual)

    saldo = monto
    cuadro = []

    for i in range(1, cuotas + 1):
        interes = saldo * tasa_mensual
        amortizacion = cuota_total - interes
        saldo -= amortizacion
        cuadro.append({
            "Cuota N°": i,
            "Cuota total ($)": round(cuota_total, 2),
            "Interés ($)": round(interes, 2),
            "Amortización ($)": round(amortizacion, 2),
            "Saldo restante ($)": round(saldo if saldo > 0 else 0, 2)
        })

    return pd.DataFrame(cuadro)


# --- Interfaz gráfica ---

def cargar_pdf():
    file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if file_path:
        #bruto, neto = extraer_sueldos(file_path)
        bruto, _, neto, _ = calcular_bloques_forzado(file_path)


        entry_bruto.config(state="normal")
        entry_neto.config(state="normal")
        entry_bruto.delete(0, tk.END)
        entry_neto.delete(0, tk.END)

        if bruto is not None and neto is not None:
            entry_bruto.insert(0, str(bruto))
            entry_neto.insert(0, str(neto))
            entry_bruto.config(state="readonly")
            entry_neto.config(state="readonly")
        else:
            messagebox.showwarning("Datos no encontrados",
                                   "No se pudieron extraer los datos del PDF. Por favor ingréselos manualmente.")
            entry_bruto.config(state="normal")
            entry_neto.config(state="normal")

def simular():
    try:
        bruto = float(entry_bruto.get())
        neto = float(entry_neto.get())
        monto = float(entry_monto.get())
        cuotas = int(entry_cuotas.get())
        tasa_base = float(entry_tasa_base.get())
        tasa_desc = float(entry_descuento.get())

        if cuotas < 1 or cuotas > 18:
            messagebox.showwarning("Regla incumplida", "La cantidad de cuotas debe ser entre 1 y 18.")
            return

        fecha = datetime.strptime(entry_fecha.get(), "%Y-%m-%d")

        if monto > 3 * bruto:
            messagebox.showwarning("Regla incumplida", "El monto excede 3 veces el sueldo bruto.")
            return

        tasa_final = tasa_base * (1 - tasa_desc / 100)
        cuota = calcular_cuota(monto, cuotas, tasa_final)

        if cuota > 0.3 * neto:
            messagebox.showwarning("Regla incumplida", "La cuota mensual excede el 30% del sueldo neto.")
            return

        # Mostrar resumen de simulación
        messagebox.showinfo(
            "Simulación exitosa",
            f"Monto solicitado: ${monto:,.2f}\n"
            f"Cantidad de cuotas: {cuotas}\n"
            f"Cuota mensual estimada: ${cuota:,.2f}\n"
            f"Tasa base anual: {tasa_base:.2f}%\n"
            f"Descuento aplicado: {tasa_desc:.2f}%\n"
            f"Tasa efectiva usada: {tasa_final:.2f}%\n\n"
            f"⚠ Recordatorio:\n"
            f"- Presentar la nota de solicitud firmada antes del miércoles.\n"
            f"- El adelanto se acredita dentro de las 48 h hábiles.\n"
            f"- Cancelación anticipada (parcial o total) está permitida.\n"
            f"- La tasa simulada es orientativa y puede variar mensualmente."
        )

        # Generar y mostrar cuadro de amortización
        df_amort = generar_cuadro_amortizacion(monto, cuotas, tasa_final)

        # Mostrar en nueva ventana de tabla
        top = tk.Toplevel()
        top.title("Cuadro de Amortización")
        from pandastable import Table
        pt = Table(top, dataframe=df_amort)
        pt.show()

    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error: {e}")




# Crear ventana principal
root = tk.Tk()
root.title("Simulador de Adelanto de Haberes")

# Widgets

tk.Button(root, text="Cargar recibo PDF", command=cargar_pdf).grid(row=0, column=0, columnspan=2, pady=10)

tk.Label(root, text="Sueldo Bruto:").grid(row=1, column=0)
entry_bruto = tk.Entry(root, state="readonly")
entry_bruto.grid(row=1, column=1)

tk.Label(root, text="Sueldo Neto:").grid(row=2, column=0)
entry_neto = tk.Entry(root, state="readonly")
entry_neto.grid(row=2, column=1)

tk.Label(root, text="Monto solicitado:").grid(row=3, column=0)
entry_monto = tk.Entry(root)
entry_monto.grid(row=3, column=1)

tk.Label(root, text="Cantidad de cuotas:").grid(row=4, column=0)
entry_cuotas = tk.Entry(root)
entry_cuotas.grid(row=4, column=1)

tk.Label(root, text="Tase base:").grid(row=5, column=0)
entry_tasa_base = tk.Entry(root)
entry_tasa_base.grid(row=5, column=1)

tk.Label(root, text="Tasa descuento:").grid(row=6, column=0)
entry_descuento = tk.Entry(root)
entry_descuento.grid(row=6, column=1)

tk.Label(root, text="Fecha simulación (YYYY-MM-DD):").grid(row=7, column=0)
entry_fecha = tk.Entry(root)
entry_fecha.grid(row=7, column=1)

tk.Button(root, text="Simular préstamo", command=simular).grid(row=8, column=0, columnspan=2, pady=10)

# Ejecutar app
root.mainloop()
