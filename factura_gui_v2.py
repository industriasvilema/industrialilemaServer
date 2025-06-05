import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from fpdf import FPDF
import os
from datetime import datetime
import requests
import threading


class FacturaGUI:
    def __init__(self, root, json_data=None):
        self.root = root
        self.root.title("Sistema de Facturación y Órdenes de Trabajo")
        self.root.geometry("1024x800")

        # Cargar datos desde JSON o crear estructura vacía
        if json_data:
            self.data = json_data
        else:
            self.data = {
                'cliente': {
                    'nombre': '',
                    'direccion': '',
                    'direccion_instalacion': '',
                    'ciudad': '',
                    'telefono': '',
                    'correo': '',
                    'cedula_ruc': ''
                },
                'contrato': {
                    'codigo': '',
                    'fecha_contrato': '',
                    'fecha_entrega': '',
                    'observacion': '',
                    'area_aluminio': False,
                    'area_enrollables': False,
                    'area_torno': False,
                    'area_cerrajeria': False
                },
                'productos': [],
                'facturacion': {
                    'subtotal': '',
                    'iva': '',
                    'total': ''
                },
                'pago': {
                    'forma_pago': '',
                    'banco': '',
                    'referencia': '',
                    'fecha_pago': '',
                    'monto_pagado': ''
                },
                'responsables': {
                    'operario': '',
                    'responsable_medicion': ''
                }
            }

        # Configurar estilos
        self.style = ttk.Style()
        self.style.configure('Title.TLabel', font=(
            'Times New Roman', 14, 'bold'))
        self.style.configure('Normal.TLabel', font=('Times New Roman', 12))
        self.style.configure('Header.TLabel', font=(
            'Times New Roman', 12, 'bold'))
        self.style.configure('Contract.TLabel', font=(
            'Times New Roman', 16, 'bold'))
        self.style.configure('Red.TLabel', font=(
            'Times New Roman', 14, 'bold'), foreground='red')

        # Variables para campos editables
        self.vars = {}

        # Variables para áreas de producción
        self.areas_produccion = {
            'ÁREA DE ALUMINIO Y VIDRIO': tk.BooleanVar(value=self.data['contrato']['area_aluminio']),
            'ÁREA DE ENROLLABLES': tk.BooleanVar(value=self.data['contrato']['area_enrollables']),
            'ÁREA DE TORNO Y MECANIZADO': tk.BooleanVar(value=self.data['contrato']['area_torno']),
            'ÁREA DE CERRAJERIA': tk.BooleanVar(value=self.data['contrato']['area_cerrajeria'])
        }

        # Crear notebook para pestañas
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=5)

        # Crear pestañas
        self.crear_tab_cliente()
        self.crear_tab_contrato()
        self.crear_tab_productos()
        self.crear_tab_facturacion()
        self.crear_tab_vista_previa()
        self.crear_tab_orden_trabajo()

        # Frame para botones y fecha
        self.frame_botones = ttk.Frame(root)
        self.frame_botones.pack(fill='x', padx=10, pady=5)

        # Botones
        self.btn_cargar = ttk.Button(
            self.frame_botones,
            text="Cargar Nueva Factura",
            command=self.cargar_factura
        )
        self.btn_cargar.pack(side='left', padx=5)

        self.btn_guardar = ttk.Button(
            self.frame_botones,
            text="Guardar Cambios",
            command=self.guardar_cambios
        )
        self.btn_guardar.pack(side='left', padx=5)

        self.btn_pdf = ttk.Button(
            self.frame_botones,
            text="Generar PDF Contrato",
            command=self.generar_pdf
        )
        self.btn_pdf.pack(side='left', padx=5)
        self.btn_pdf.configure(state='disabled' if not any(
            var.get() for var in self.areas_produccion.values()) else 'normal')

        self.btn_orden = ttk.Button(
            self.frame_botones,
            text="Generar PDF Orden",
            command=self.generar_pdf_orden
        )
        self.btn_orden.pack(side='left', padx=5)
        self.btn_orden.configure(state='disabled' if not any(
            var.get() for var in self.areas_produccion.values()) else 'normal')

        # Mostrar fecha actual
        self.lbl_fecha = ttk.Label(
            self.frame_botones,
            text=f"Fecha: {datetime.now().strftime('%d/%m/%Y')}",
            font=('Times New Roman', 12)
        )
        self.lbl_fecha.pack(side='right', padx=5)

    def cargar_factura(self):
        """Carga una nueva factura mediante una imagen"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar imagen de factura",
            filetypes=[("Imágenes", "*.jpg;*.jpeg;*.png")]
        )

        if not file_path:
            return

        # Mostrar mensaje de procesamiento
        self.processing_msg = tk.Toplevel(self.root)
        self.processing_msg.title("Procesando")
        self.processing_msg.geometry("300x100")
        ttk.Label(self.processing_msg,
                  text="Procesando factura...").pack(pady=20)
        self.processing_msg.grab_set()

        # Ejecutar en un hilo para no bloquear la GUI
        threading.Thread(
            target=self.enviar_factura_al_servidor,
            args=(file_path,),
            daemon=True
        ).start()

    def enviar_factura_al_servidor(self, file_path):
        """Envía la factura al endpoint /predict para procesamiento"""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    "http://localhost:8080/predict",
                    files=files
                )
                response.raise_for_status()
                new_data = response.json()

                # Actualizar los datos en la GUI
                self.root.after(0, self.actualizar_interfaz, new_data)

        except Exception as e:
            self.root.after(0, messagebox.showerror,
                            "Error",
                            f"Error al procesar factura: {str(e)}")
        finally:
            self.root.after(0, self.processing_msg.destroy)

    def actualizar_interfaz(self, new_data):
        """Actualiza toda la interfaz con nuevos datos"""
        self.data = new_data

        # Actualizar variables de áreas de producción
        self.areas_produccion['ÁREA DE ALUMINIO Y VIDRIO'].set(
            self.data['contrato'].get('area_aluminio', False))
        self.areas_produccion['ÁREA DE ENROLLABLES'].set(
            self.data['contrato'].get('area_enrollables', False))
        self.areas_produccion['ÁREA DE TORNO Y MECANIZADO'].set(
            self.data['contrato'].get('area_torno', False))
        self.areas_produccion['ÁREA DE CERRAJERIA'].set(
            self.data['contrato'].get('area_cerrajeria', False))

        # Destruir todas las pestañas existentes
        for child in self.notebook.winfo_children():
            child.destroy()

        # Volver a crear las pestañas con los nuevos datos
        self.crear_tab_cliente()
        self.crear_tab_contrato()
        self.crear_tab_productos()
        self.crear_tab_facturacion()
        self.crear_tab_vista_previa()
        self.crear_tab_orden_trabajo()

        # Actualizar estado de botones PDF
        self.actualizar_botones_pdf()

        messagebox.showinfo("Éxito", "Factura procesada correctamente")

    def crear_campo_editable(self, parent, key, valor, row, column=1):
        """Crear un campo de entrada editable con etiqueta"""
        if isinstance(valor, (dict, list)):
            return None

        var = tk.StringVar(value=str(valor if valor is not None else ""))
        self.vars[key] = var
        entry = ttk.Entry(parent, textvariable=var, font=(
            'Times New Roman', 12), width=40)
        entry.grid(row=row, column=column, padx=5, pady=5, sticky='w')
        return entry

    def crear_tab_cliente(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Datos del Cliente")

        ttk.Label(tab, text="Información del Cliente", style='Title.TLabel').grid(
            row=0, column=0, columnspan=2, pady=10)

        cliente = self.data['cliente']
        row = 1

        for key, valor in cliente.items():
            label_text = key.replace('_', ' ').title() + ":"
            ttk.Label(tab, text=label_text, style='Header.TLabel').grid(
                row=row, column=0, padx=5, pady=5, sticky='e')
            self.crear_campo_editable(tab, f"cliente.{key}", valor, row)
            row += 1

    def crear_tab_contrato(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Datos del Contrato")

        # Scrollable frame
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        frame_scroll = ttk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame_scroll, anchor="nw")

        ttk.Label(frame_scroll, text="Información del Contrato",
                  style='Title.TLabel').grid(row=0, column=0, columnspan=2, pady=10)

        # Datos del contrato
        contrato = self.data['contrato']
        row = 1

        for key, valor in contrato.items():
            if key.startswith('area_'):  # Saltar campos de área
                continue

            label_text = key.replace('_', ' ').title() + ":"
            ttk.Label(frame_scroll, text=label_text,
                      style='Header.TLabel').grid(row=row, column=0, padx=5, pady=5, sticky='e')
            self.crear_campo_editable(
                frame_scroll, f"contrato.{key}", valor, row)
            row += 1

        # Áreas de producción
        row += 1
        ttk.Label(frame_scroll, text="Áreas de Producción",
                  style='Title.TLabel').grid(row=row, column=0, columnspan=2, pady=(20, 10))

        # Frame para los checkboxes
        frame_areas = ttk.Frame(frame_scroll)
        frame_areas.grid(row=row+1, column=0, columnspan=2, padx=20, pady=5)

        for i, (area, var) in enumerate(self.areas_produccion.items()):
            cb = ttk.Checkbutton(frame_areas, text=area, variable=var,
                                 command=self.actualizar_botones_pdf)
            cb.grid(row=i//2, column=i % 2, padx=10, pady=5, sticky='w')

        # Actualizar scroll region
        frame_scroll.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def actualizar_botones_pdf(self):
        """Actualiza el estado de los botones PDF según las áreas seleccionadas"""
        areas_seleccionadas = any(var.get()
                                  for var in self.areas_produccion.values())
        self.btn_pdf.configure(
            state='normal' if areas_seleccionadas else 'disabled')
        self.btn_orden.configure(
            state='normal' if areas_seleccionadas else 'disabled')

    def crear_tab_productos(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Productos")

        ttk.Label(tab, text="Lista de Productos", style='Title.TLabel').grid(
            row=0, column=0, columnspan=2, pady=10)

        # Frame para la tabla
        frame_tabla = ttk.Frame(tab)
        frame_tabla.grid(row=1, column=0, columnspan=2,
                         sticky='nsew', padx=5, pady=5)

        # Crear Treeview con scrollbar
        columns = ('Cantidad', 'Código', 'Detalle',
                   'Valor Unitario', 'Valor Total')
        tree = ttk.Treeview(frame_tabla, columns=columns,
                            show='headings', height=10)
        scrollbar = ttk.Scrollbar(
            frame_tabla, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        # Configurar columnas
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        tree.column('Detalle', width=300)

        # Insertar productos
        for producto in self.data['productos']:
            valores = (
                producto['cantidad'],
                producto['codigo'] or "",
                producto['detalle'] or "",
                producto['valor_unitario'] or "",
                producto['valor_total'] or ""
            )
            item = tree.insert('', 'end', values=valores)
            # Hacer el item editable con doble clic
            tree.tag_bind(item, '<Double-1>', lambda e,
                          item=item: self.editar_producto(tree, item))

        # Botones para agregar/eliminar productos
        frame_botones = ttk.Frame(frame_tabla)
        frame_botones.grid(row=1, column=0, columnspan=2, pady=5)

        ttk.Button(frame_botones, text="Agregar Producto",
                   command=lambda: self.agregar_producto(tree)).pack(side='left', padx=5)
        ttk.Button(frame_botones, text="Eliminar Producto",
                   command=lambda: self.eliminar_producto(tree)).pack(side='left')

        tree.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

        # Configurar expansión
        frame_tabla.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

    def editar_producto(self, tree, item):
        # Crear ventana de edición
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Editar Producto")
        edit_window.geometry("500x300")

        valores = tree.item(item)['values']

        ttk.Label(edit_window, text="Cantidad:", style='Normal.TLabel').grid(
            row=0, column=0, padx=5, pady=5)
        cantidad = ttk.Entry(edit_window, font=('Times New Roman', 12))
        cantidad.insert(0, valores[0])
        cantidad.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(edit_window, text="Código:", style='Normal.TLabel').grid(
            row=1, column=0, padx=5, pady=5)
        codigo = ttk.Entry(edit_window, font=('Times New Roman', 12))
        codigo.insert(0, valores[1])
        codigo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(edit_window, text="Detalle:", style='Normal.TLabel').grid(
            row=2, column=0, padx=5, pady=5)
        detalle = ttk.Entry(edit_window, font=(
            'Times New Roman', 12), width=50)
        detalle.insert(0, valores[2])
        detalle.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(edit_window, text="Valor Unitario:", style='Normal.TLabel').grid(
            row=3, column=0, padx=5, pady=5)
        valor_unitario = ttk.Entry(edit_window, font=('Times New Roman', 12))
        valor_unitario.insert(0, valores[3])
        valor_unitario.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(edit_window, text="Valor Total:", style='Normal.TLabel').grid(
            row=4, column=0, padx=5, pady=5)
        valor_total = ttk.Entry(edit_window, font=('Times New Roman', 12))
        valor_total.insert(0, valores[4])
        valor_total.grid(row=4, column=1, padx=5, pady=5)

        # Botón para guardar cambios
        ttk.Button(edit_window, text="Guardar",
                   command=lambda: self.guardar_edicion_producto(
                       tree, item,
                       cantidad.get(),
                       codigo.get(),
                       detalle.get(),
                       valor_unitario.get(),
                       valor_total.get(),
                       edit_window
                   )).grid(row=5, column=0, columnspan=2, pady=20)

    def guardar_edicion_producto(self, tree, item, cantidad, codigo, detalle, valor_unitario, valor_total, window):
        tree.item(item, values=(cantidad, codigo,
                  detalle, valor_unitario, valor_total))
        window.destroy()

    def agregar_producto(self, tree):
        item = tree.insert('', 'end', values=('1', '', '', '0.00', '0.00'))
        self.editar_producto(tree, item)

    def eliminar_producto(self, tree):
        selected_items = tree.selection()
        if selected_items:
            for item in selected_items:
                tree.delete(item)

    def crear_tab_facturacion(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Facturación")

        row = 0
        # Datos de facturación
        ttk.Label(tab, text="Datos de Facturación", style='Title.TLabel').grid(
            row=row, column=0, columnspan=2, pady=10)
        row += 1

        facturacion = self.data['facturacion']
        for key, valor in facturacion.items():
            label_text = key.replace('_', ' ').title() + ":"
            ttk.Label(tab, text=label_text, style='Header.TLabel').grid(
                row=row, column=0, padx=5, pady=5, sticky='e')
            self.crear_campo_editable(tab, f"facturacion.{key}", valor, row)
            row += 1

        # Datos de pago
        row += 1
        ttk.Label(tab, text="Datos de Pago", style='Title.TLabel').grid(
            row=row, column=0, columnspan=2, pady=10)
        row += 1

        pago = self.data['pago']
        for key, valor in pago.items():
            label_text = key.replace('_', ' ').title() + ":"
            ttk.Label(tab, text=label_text, style='Header.TLabel').grid(
                row=row, column=0, padx=5, pady=5, sticky='e')
            self.crear_campo_editable(tab, f"pago.{key}", valor, row)
            row += 1

        # Responsables
        row += 1
        ttk.Label(tab, text="Responsables", style='Title.TLabel').grid(
            row=row, column=0, columnspan=2, pady=10)
        row += 1

        responsables = self.data['responsables']
        for key, valor in responsables.items():
            label_text = key.replace('_', ' ').title() + ":"
            ttk.Label(tab, text=label_text, style='Header.TLabel').grid(
                row=row, column=0, padx=5, pady=5, sticky='e')
            self.crear_campo_editable(tab, f"responsables.{key}", valor, row)
            row += 1

    def crear_tab_vista_previa(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Vista Previa")

        # Canvas para la vista previa
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        frame_preview = ttk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack los elementos
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Crear ventana en el canvas
        canvas.create_window((0, 0), window=frame_preview, anchor="nw")

        # Título
        ttk.Label(frame_preview, text="FACTURA",
                  style='Title.TLabel').pack(pady=20)

        # Fecha
        ttk.Label(frame_preview,
                  text=f"Fecha: {datetime.now().strftime('%d/%m/%Y')}",
                  style='Normal.TLabel').pack(anchor='e', padx=20)

        # Datos del cliente
        self.crear_seccion_preview(
            frame_preview, "Datos del Cliente", self.data['cliente'])
        self.crear_seccion_preview(
            frame_preview, "Datos del Contrato", self.data['contrato'])
        self.crear_tabla_productos_preview(frame_preview)
        self.crear_seccion_preview(
            frame_preview, "Facturación", self.data['facturacion'])
        self.crear_seccion_preview(
            frame_preview, "Datos de Pago", self.data['pago'])
        self.crear_seccion_preview(
            frame_preview, "Responsables", self.data['responsables'])

        # Actualizar scrollregion después de agregar widgets
        frame_preview.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def crear_seccion_preview(self, parent, titulo, datos):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(frame, text=titulo, style='Header.TLabel').pack(anchor='w')

        for key, valor in datos.items():
            if key.startswith('area_'):  # Saltar campos de área
                continue

            if valor:
                label_text = f"{key.replace('_', ' ').title()}: {valor}"
                ttk.Label(frame, text=label_text,
                          style='Normal.TLabel').pack(anchor='w')

    def crear_tabla_productos_preview(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(frame, text="Productos",
                  style='Header.TLabel').pack(anchor='w')

        # Crear tabla
        columns = ('Cantidad', 'Código', 'Detalle', 'V.Unit', 'V.Total')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=5)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        tree.column('Detalle', width=300)

        for producto in self.data['productos']:
            valores = (
                producto['cantidad'],
                producto['codigo'] or "N/A",
                producto['detalle'] or "N/A",
                producto['valor_unitario'] or "N/A",
                producto['valor_total'] or "N/A"
            )
            tree.insert('', 'end', values=valores)

        tree.pack(fill='x')

    def crear_tab_orden_trabajo(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Orden de Trabajo")

        # Frame principal con scroll
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        frame_main = ttk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame_main, anchor="nw")

        # Encabezado
        ttk.Label(frame_main, text="Industrias Metálicas Vilema - IMEV",
                  style='Title.TLabel').pack(pady=(20, 5))
        ttk.Label(frame_main, text="ORDEN DE TRABAJO",
                  style='Contract.TLabel').pack(pady=(5, 20))

        # Número de contrato en rojo
        frame_contrato = ttk.Frame(frame_main)
        frame_contrato.pack(fill='x', padx=20)
        ttk.Label(frame_contrato, text="Número de Contrato:",
                  style='Header.TLabel').pack(side='left')
        ttk.Label(frame_contrato, text=self.data['contrato']['codigo'],
                  style='Red.TLabel').pack(side='left', padx=5)

        # Fecha actual
        ttk.Label(frame_main, text=f"Fecha: {datetime.now().strftime('%d/%m/%Y')}",
                  style='Normal.TLabel').pack(anchor='e', padx=20, pady=10)

        # Campos específicos para orden de trabajo
        self.crear_seccion_orden(frame_main, "Datos del Cliente", {
            'Nombre': self.data['cliente']['nombre'],
            'Dirección Instalación': self.data['cliente']['direccion_instalacion'],
            'Ciudad': self.data['cliente']['ciudad']
        })

        self.crear_seccion_orden(frame_main, "Datos del Trabajo", {
            'Fecha Entrega': self.data['contrato']['fecha_entrega'],
            'Observaciones': self.data['contrato']['observacion']
        })

        self.crear_seccion_orden(frame_main, "Responsables", {
            'Operario': self.data['responsables'].get('operario', ''),
            'Responsable Medición': self.data['responsables'].get('responsable_medicion', '')
        })

        # Tabla de productos editable
        self.crear_tabla_productos_orden(frame_main)

        # Áreas de producción seleccionadas
        self.crear_seccion_areas_produccion(frame_main)

        # Actualizar scrollregion
        frame_main.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def crear_seccion_areas_produccion(self, parent):
        """Muestra las áreas de producción seleccionadas"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(frame, text="Áreas de Producción Asignadas:",
                  style='Header.TLabel').pack(anchor='w', pady=(0, 5))

        areas_seleccionadas = [area for area,
                               var in self.areas_produccion.items() if var.get()]
        if areas_seleccionadas:
            for area in areas_seleccionadas:
                ttk.Label(frame, text=f"• {area}",
                          style='Normal.TLabel').pack(anchor='w', padx=20)
        else:
            ttk.Label(frame, text="No se han seleccionado áreas de producción",
                      style='Normal.TLabel').pack(anchor='w', padx=20)

    def crear_tabla_productos_orden(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(frame, text="Productos", style='Header.TLabel').pack(
            anchor='w', pady=(0, 5))

        # Crear tabla
        columns = ('Cantidad', 'Código', 'Detalle')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=5)

        # Configurar columnas
        tree.heading('Cantidad', text='Cantidad')
        tree.heading('Código', text='Código')
        tree.heading('Detalle', text='Detalle')

        tree.column('Cantidad', width=100)
        tree.column('Código', width=100)
        tree.column('Detalle', width=500)

        # Insertar productos
        for producto in self.data['productos']:
            valores = (
                producto['cantidad'],
                producto['codigo'] or "",
                producto['detalle'] or ""
            )
            item = tree.insert('', 'end', values=valores)

            # Hacer editable
            tree.tag_bind(item, '<Double-1>', lambda e,
                          item=item: self.editar_producto_orden(tree, item))

        tree.pack(fill='x', pady=5)

        # Botones para agregar/eliminar productos
        frame_botones = ttk.Frame(frame)
        frame_botones.pack(fill='x', pady=5)

        ttk.Button(frame_botones, text="Agregar Producto",
                   command=lambda: self.agregar_producto_orden(tree)).pack(side='left', padx=5)
        ttk.Button(frame_botones, text="Eliminar Producto",
                   command=lambda: self.eliminar_producto_orden(tree)).pack(side='left')

    def editar_producto_orden(self, tree, item):
        # Crear ventana de edición
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Editar Producto")
        edit_window.geometry("500x200")

        valores = tree.item(item)['values']

        ttk.Label(edit_window, text="Cantidad:", style='Normal.TLabel').grid(
            row=0, column=0, padx=5, pady=5)
        cantidad = ttk.Entry(edit_window, font=('Times New Roman', 12))
        cantidad.insert(0, valores[0])
        cantidad.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(edit_window, text="Código:", style='Normal.TLabel').grid(
            row=1, column=0, padx=5, pady=5)
        codigo = ttk.Entry(edit_window, font=('Times New Roman', 12))
        codigo.insert(0, valores[1])
        codigo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(edit_window, text="Detalle:", style='Normal.TLabel').grid(
            row=2, column=0, padx=5, pady=5)
        detalle = ttk.Entry(edit_window, font=(
            'Times New Roman', 12), width=50)
        detalle.insert(0, valores[2])
        detalle.grid(row=2, column=1, padx=5, pady=5)

        # Botón para guardar cambios
        ttk.Button(edit_window, text="Guardar",
                   command=lambda: self.guardar_edicion_producto(tree, item, cantidad.get(), codigo.get(),
                                                                 detalle.get(), edit_window)).grid(row=3, column=0, columnspan=2, pady=20)

    def guardar_edicion_producto(self, tree, item, cantidad, codigo, detalle, window):
        tree.item(item, values=(cantidad, codigo, detalle))
        window.destroy()

    def agregar_producto_orden(self, tree):
        item = tree.insert('', 'end', values=('', '', ''))
        self.editar_producto_orden(tree, item)

    def eliminar_producto_orden(self, tree):
        selected_item = tree.selection()
        if selected_item:
            tree.delete(selected_item)

    def guardar_cambios(self):
        # Actualizar datos desde los campos de entrada
        for key, var in self.vars.items():
            seccion, campo = key.split('.')
            self.data[seccion][campo] = var.get()

        # Actualizar áreas de producción en contrato
        self.data['contrato']['area_aluminio'] = self.areas_produccion['ÁREA DE ALUMINIO Y VIDRIO'].get()
        self.data['contrato']['area_enrollables'] = self.areas_produccion['ÁREA DE ENROLLABLES'].get()
        self.data['contrato']['area_torno'] = self.areas_produccion['ÁREA DE TORNO Y MECANIZADO'].get()
        self.data['contrato']['area_cerrajeria'] = self.areas_produccion['ÁREA DE CERRAJERIA'].get()

        # Actualizar la pestaña de vista previa
        self.notebook.forget(4)  # Eliminar la pestaña de vista previa
        self.crear_tab_vista_previa()  # Volver a crear con datos actualizados
        self.notebook.add(self.notebook.winfo_children()[
                          4], text="Vista Previa")  # Reinsertar en su posición

        messagebox.showinfo(
            "Éxito", "Los cambios se han guardado correctamente")

    def generar_pdf(self):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Configuración de fuente
        pdf.add_font('Times', '', r'C:\Windows\Fonts\times.ttf', uni=True)
        pdf.add_font('Times', 'B', r'C:\Windows\Fonts\timesbd.ttf', uni=True)

        # Título
        pdf.set_font('Times', 'B', 16)
        pdf.cell(190, 10, "FACTURA", ln=True, align='C')
        pdf.line(10, 30, 200, 30)

        # Fecha
        pdf.set_font('Times', '', 12)
        pdf.cell(
            190, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')

        # Datos del cliente
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Datos del Cliente", ln=True)
        pdf.set_font('Times', '', 12)

        cliente = self.data['cliente']
        for key, valor in cliente.items():
            label = key.replace('_', ' ').title()
            pdf.multi_cell(190, 7, f"{label}: {valor if valor else 'N/A'}")

        # Datos del contrato
        pdf.ln(5)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Datos del Contrato", ln=True)
        pdf.set_font('Times', '', 12)

        contrato = self.data['contrato']
        for key, valor in contrato.items():
            if key.startswith('area_'):  # Saltar campos de área
                continue
            label = key.replace('_', ' ').title()
            pdf.multi_cell(190, 7, f"{label}: {valor if valor else 'N/A'}")

        # Productos
        pdf.ln(5)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Productos", ln=True)

        # Encabezados de tabla
        cols = ['Cant.', 'Código', 'Detalle', 'V.Unit', 'V.Total']
        widths = [20, 30, 80, 30, 30]
        pdf.set_font('Times', 'B', 12)

        for i, col in enumerate(cols):
            pdf.cell(widths[i], 7, col, border=1)
        pdf.ln()

        # Datos de productos
        pdf.set_font('Times', '', 10)
        for producto in self.data['productos']:
            pdf.cell(20, 7, str(producto['cantidad']), border=1)
            pdf.cell(30, 7, str(producto['codigo'] or "N/A"), border=1)
            pdf.cell(80, 7, str(producto['detalle'] or "N/A"), border=1)
            pdf.cell(30, 7, str(producto['valor_unitario'] or "N/A"), border=1)
            pdf.cell(30, 7, str(producto['valor_total'] or "N/A"), border=1)
            pdf.ln()

        # Datos de facturación
        pdf.ln(5)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Facturación", ln=True)
        pdf.set_font('Times', '', 12)

        facturacion = self.data['facturacion']
        for key, valor in facturacion.items():
            label = key.replace('_', ' ').title()
            pdf.cell(190, 7, f"{label}: {valor if valor else 'N/A'}", ln=True)

        # Datos de pago y responsables
        pdf.ln(5)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Datos de Pago y Responsables", ln=True)
        pdf.set_font('Times', '', 12)

        pago = self.data['pago']
        responsables = self.data['responsables']

        for key, valor in pago.items():
            label = key.replace('_', ' ').title()
            pdf.cell(190, 7, f"{label}: {valor if valor else 'N/A'}", ln=True)

        pdf.ln(5)
        for key, valor in responsables.items():
            label = key.replace('_', ' ').title()
            pdf.cell(190, 7, f"{label}: {valor if valor else 'N/A'}", ln=True)

        # Guardar PDF
        nombre_archivo = f"factura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf.output(nombre_archivo)
        os.startfile(nombre_archivo)  # Abrir el PDF automáticamente

    def generar_pdf_orden(self):
        # Verificar áreas seleccionadas
        areas_seleccionadas = [area for area,
                               var in self.areas_produccion.items() if var.get()]
        if not areas_seleccionadas:
            messagebox.showwarning("Advertencia",
                                   "Debe seleccionar al menos un área de producción antes de generar la orden.")
            return

        # Mostrar confirmación
        areas_texto = "\n".join(f"• {area}" for area in areas_seleccionadas)
        if not messagebox.askyesno("Confirmar Impresión",
                                   f"¿Desea generar la orden de trabajo para las siguientes áreas?\n\n{areas_texto}"):
            return

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Configuración de fuente
        pdf.add_font('Times', '', r'C:\Windows\Fonts\times.ttf', uni=True)
        pdf.add_font('Times', 'B', r'C:\Windows\Fonts\timesbd.ttf', uni=True)

        # Encabezado
        pdf.set_font('Times', 'B', 16)
        pdf.cell(190, 10, "Industrias Metálicas Vilema - IMEV",
                 ln=True, align='C')
        pdf.set_font('Times', 'B', 18)
        pdf.cell(190, 10, "ORDEN DE TRABAJO", ln=True, align='C')
        pdf.line(10, 40, 200, 40)

        # Número de contrato en rojo
        pdf.set_text_color(255, 0, 0)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(
            190, 10, f"Número de Contrato: {self.data['contrato']['codigo']}", ln=True, align='R')
        pdf.set_text_color(0, 0, 0)

        # Fecha
        pdf.set_font('Times', '', 12)
        pdf.cell(
            190, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')

        # Datos del cliente
        pdf.ln(5)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Datos del Cliente", ln=True)
        pdf.set_font('Times', '', 12)

        cliente = self.data['cliente']
        datos_cliente = [
            f"Nombre: {cliente['nombre']}",
            f"Dirección: {cliente['direccion']}",
            f"Dirección Instalación: {cliente['direccion_instalacion']}",
            f"Ciudad: {cliente['ciudad']}",
            f"Teléfono: {cliente['telefono']}"
        ]

        for dato in datos_cliente:
            pdf.multi_cell(190, 7, dato)

        # Datos del contrato
        pdf.ln(5)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Datos del Contrato", ln=True)
        pdf.set_font('Times', '', 12)

        contrato = self.data['contrato']
        datos_contrato = [
            f"Fecha de Inicio: {contrato['fecha_contrato']}",
            f"Fecha de Entrega: {contrato['fecha_entrega']}",
            f"Observaciones: {contrato['observacion']}"
        ]

        for dato in datos_contrato:
            pdf.multi_cell(190, 7, dato)

        # Tabla de productos
        pdf.ln(5)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Productos", ln=True)

        # Encabezados de tabla
        cols = ['Cant.', 'Código', 'Detalle']
        widths = [20, 30, 140]
        pdf.set_font('Times', 'B', 12)

        for i, col in enumerate(cols):
            pdf.cell(widths[i], 7, col, border=1)
        pdf.ln()

        # Datos de productos
        pdf.set_font('Times', '', 10)
        for producto in self.data['productos']:
            pdf.cell(20, 7, str(producto['cantidad']), border=1)
            pdf.cell(30, 7, str(producto['codigo'] or ""), border=1)
            pdf.cell(140, 7, str(producto['detalle'] or ""), border=1)
            pdf.ln()

        # Áreas de producción asignadas
        pdf.ln(10)
        pdf.set_font('Times', 'B', 14)
        pdf.cell(190, 10, "Áreas de Producción Asignadas", ln=True)
        pdf.set_font('Times', '', 12)

        for area in areas_seleccionadas:
            pdf.cell(190, 7, f"• {area}", ln=True)

        # Responsables
        pdf.ln(15)
        pdf.set_font('Times', 'B', 12)

        # Crear líneas para firmas
        y_firmas = pdf.get_y()
        pdf.line(20, y_firmas, 90, y_firmas)
        pdf.line(120, y_firmas, 190, y_firmas)

        pdf.set_y(y_firmas + 5)
        pdf.cell(90, 10, "Operario", align='C')
        pdf.cell(20)
        pdf.cell(90, 10, "Responsable de Medición", align='C')

        pdf.set_y(y_firmas - 15)
        pdf.set_font('Times', '', 10)
        responsables = self.data['responsables']
        pdf.cell(90, 10, str(responsables.get('operario', '')), align='C')
        pdf.cell(20)
        pdf.cell(90, 10, str(responsables.get(
            'responsable_medicion', '')), align='C')

        # Guardar PDF y preguntar si desea abrirlo
        nombre_archivo = f"orden_trabajo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf.output(nombre_archivo)
        if messagebox.askyesno("PDF Generado",
                               f"La orden de trabajo se ha guardado como:\n{nombre_archivo}\n\n¿Desea abrirla?"):
            os.startfile(nombre_archivo)

    def crear_seccion_orden(self, parent, titulo, datos):
        """Crea una sección en la orden de trabajo"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(frame, text=titulo, style='Header.TLabel').pack(
            anchor='w', pady=(0, 5))

        for key, valor in datos.items():
            if valor:
                label_text = f"{key}: {valor}"
                ttk.Label(frame, text=label_text, style='Normal.TLabel').pack(
                    anchor='w', padx=20)


if __name__ == "__main__":
    json_data = None
    # Verificar si se proporcionó un archivo JSON como argumento
    if len(sys.argv) > 1 and sys.argv[1].endswith('.json'):
        try:
            with open(sys.argv[1], 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except Exception as e:
            print(f"Error al cargar archivo JSON: {e}")
            json_data = None
    root = tk.Tk()
    app = FacturaGUI(root, json_data)
    root.mainloop()
