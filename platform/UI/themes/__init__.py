import os

def load_theme(theme_name: str) -> str:
    """
    Carga y retorna el contenido de un archivo QSS de tema.
    
    Args:
        theme_name (str): Nombre del tema ('dark' o 'light')
        
    Returns:
        str: Contenido del archivo QSS como string
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    theme_file = os.path.join(current_dir, f"{theme_name}_theme.qss")
    
    try:
        with open(theme_file, 'r', encoding='utf-8') as f:
            qss = f.read()
        # Reemplazar el placeholder __THEME_DIR__ con la ruta real
        # Usar forward slashes para compatibilidad con Qt stylesheet url()
        theme_dir_path = current_dir.replace("\\", "/")
        qss = qss.replace("__THEME_DIR__", theme_dir_path)
        return qss
    except Exception as e:
        print(f"Error cargando el tema {theme_name}: {e}")
        return ""

