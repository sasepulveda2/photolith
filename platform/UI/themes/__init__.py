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
            return f.read()
    except Exception as e:
        print(f"Error cargando el tema {theme_name}: {e}")
        return ""
