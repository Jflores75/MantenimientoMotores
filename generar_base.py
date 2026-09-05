import pandas as pd

datos = {
    'Equipo': ['Bomba-101', 'Faja-201', 'Compresor-301', 'Molino-401', 'Bomba-102', 'Faja-202', 'Compresor-302', 'Molino-402'],
    'Tipo_Equipo': ['Bomba Centrífuga', 'Faja Transportadora', 'Compresor', 'Molino', 'Bomba Centrífuga', 'Faja Transportadora', 'Compresor', 'Molino'],
    'Temperatura_C': [60.0, 45.0, 78.0, 65.0, 85.0, 70.0, 90.0, 60.0],
    'Vibracion_mm_s': [2.1, 1.8, 3.5, 6.5, 5.2, 4.0, 6.1, 2.0],
    'Amperaje_A': [18.5, 12.0, 40.0, 85.0, 24.0, 18.0, 50.0, 80.0],
    'Horas_Operacion': [4200, 5000, 1100, 2900, 7800, 6800, 7500, 1500] 
}

pd.DataFrame(datos).to_excel('inventario_planta.xlsx', index=False)
print("✅ Archivo 'inventario_planta.xlsx' actualizado con 8 equipos.")