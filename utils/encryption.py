#!/usr/bin/env python3
"""
Módulo de encriptación/desencriptación para archivos .env
Utiliza AES-256-GCM para encriptación simétrica segura
"""

import os
import base64
import json
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)

class EnvEncryption:
    """Clase para manejar encriptación/desencriptación de archivos .env"""
    
    def __init__(self, master_password: Optional[str] = None):
        """
        Inicializa el gestor de encriptación
        
        Args:
            master_password: Contraseña maestra para derivar clave de encriptación.
                           Si no se proporciona, usa variable de entorno ENV_MASTER_PASSWORD
        """
        self.master_password = master_password or os.getenv('ENV_MASTER_PASSWORD', 'default_master_key_2024')
        self.salt = b'NewsPilot_env_salt_2024'  # Salt fijo para consistencia
        self.key = self._derive_key()
    
    def _derive_key(self) -> bytes:
        """
        Deriva clave de encriptación a partir de la contraseña maestra usando PBKDF2
        
        Returns:
            Clave de 32 bytes para AES-256
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits para AES-256
            salt=self.salt,
            iterations=100000,  # Iteraciones para seguridad
            backend=default_backend()
        )
        return kdf.derive(self.master_password.encode())
    
    def encrypt_env_content(self, env_content: str) -> str:
        """
        Encripta el contenido de un archivo .env
        
        Args:
            env_content: Contenido del archivo .env como texto plano
            
        Returns:
            Contenido encriptado codificado en base64
        """
        try:
            # Convertir contenido a bytes
            env_bytes = env_content.encode('utf-8')
            
            # Generar nonce único para cada encriptación
            nonce = os.urandom(12)  # 96 bits para GCM
            
            # Encriptar usando AES-GCM
            aesgcm = AESGCM(self.key)
            encrypted = aesgcm.encrypt(nonce, env_bytes, None)  # No additional data
            
            # Combinar nonce + encrypted y codificar en base64
            combined = nonce + encrypted
            encrypted_b64 = base64.b64encode(combined).decode('utf-8')
            
            logger.info("✅ Contenido .env encriptado exitosamente")
            return encrypted_b64
            
        except Exception as e:
            logger.error(f"❌ Error encriptando contenido .env: {str(e)}")
            raise
    
    def decrypt_env_content(self, encrypted_content: str) -> str:
        """
        Desencripta el contenido de un archivo .env
        
        Args:
            encrypted_content: Contenido encriptado codificado en base64
            
        Returns:
            Contenido del archivo .env como texto plano
        """
        try:
            # Decodificar de base64
            combined = base64.b64decode(encrypted_content.encode('utf-8'))
            
            # Extraer nonce (primeros 12 bytes) y contenido encriptado
            nonce = combined[:12]
            encrypted = combined[12:]
            
            # Desencriptar usando AES-GCM
            aesgcm = AESGCM(self.key)
            decrypted_bytes = aesgcm.decrypt(nonce, encrypted, None)
            
            # Convertir a string
            env_content = decrypted_bytes.decode('utf-8')
            
            logger.info("✅ Contenido .env desencriptado exitosamente")
            return env_content
            
        except Exception as e:
            logger.error(f"❌ Error desencriptando contenido .env: {str(e)}")
            raise
    
    def parse_env_content(self, env_content: str) -> Dict[str, str]:
        """
        Parsea el contenido de un archivo .env a un diccionario
        
        Args:
            env_content: Contenido del archivo .env
            
        Returns:
            Diccionario con variables de entorno
        """
        env_dict = {}
        
        for line in env_content.split('\n'):
            line = line.strip()
            
            # Ignorar líneas vacías y comentarios
            if not line or line.startswith('#'):
                continue
            
            # Buscar el primer '=' que no esté escapado
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remover comillas si existen
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                env_dict[key] = value
        
        return env_dict
    
    def format_env_content(self, env_dict: Dict[str, str]) -> str:
        """
        Formatea un diccionario a contenido de archivo .env
        
        Args:
            env_dict: Diccionario con variables de entorno
            
        Returns:
            Contenido formateado como archivo .env
        """
        lines = []
        
        # Ordenar claves alfabéticamente para consistencia
        for key in sorted(env_dict.keys()):
            value = env_dict[key]
            
            # Si el valor contiene espacios o caracteres especiales, entrecomillar
            if any(char in value for char in [' ', '#', '$', '"', "'"]) and value:
                value = f'"{value}"'
            
            lines.append(f"{key}={value}")
        
        return '\n'.join(lines)
    
    def encrypt_env_file(self, file_path: str) -> bool:
        """
        Encripta un archivo .env existente
        
        Args:
            file_path: Ruta al archivo .env
            
        Returns:
            True si la encriptación fue exitosa
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"❌ Archivo no encontrado: {file_path}")
                return False
            
            # Leer contenido original
            with open(file_path, 'r', encoding='utf-8') as f:
                env_content = f.read()
            
            # Encriptar contenido
            encrypted_content = self.encrypt_env_content(env_content)
            
            # Sobrescribir archivo con contenido encriptado
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_content)
            
            logger.info(f"✅ Archivo {file_path} encriptado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error encriptando archivo {file_path}: {str(e)}")
            return False
    
    def decrypt_env_file(self, file_path: str) -> Optional[str]:
        """
        Desencripta un archivo .env encriptado
        
        Args:
            file_path: Ruta al archivo .env encriptado
            
        Returns:
            Contenido desencriptado o None si hay error
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"❌ Archivo no encontrado: {file_path}")
                return None
            
            # Leer contenido encriptado
            with open(file_path, 'r', encoding='utf-8') as f:
                encrypted_content = f.read()
            
            # Verificar si parece estar encriptado (base64)
            try:
                base64.b64decode(encrypted_content.encode('utf-8'))
                is_encrypted = True
            except Exception:
                is_encrypted = False
            
            if not is_encrypted:
                # Si no está encriptado, retornar contenido tal cual
                logger.info(f"📄 Archivo {file_path} no parece estar encriptado")
                return encrypted_content
            
            # Desencriptar contenido
            decrypted_content = self.decrypt_env_content(encrypted_content)
            
            logger.info(f"✅ Archivo {file_path} desencriptado exitosamente")
            return decrypted_content
            
        except Exception as e:
            logger.error(f"❌ Error desencriptando archivo {file_path}: {str(e)}")
            return None
    
    def save_encrypted_env(self, file_path: str, env_dict: Dict[str, str]) -> bool:
        """
        Guarda un diccionario de variables de entorno en archivo .env encriptado
        
        Args:
            file_path: Ruta donde guardar el archivo
            env_dict: Diccionario con variables de entorno
            
        Returns:
            True si el guardado fue exitoso
        """
        try:
            # Formatear a contenido .env
            env_content = self.format_env_content(env_dict)
            
            # Encriptar contenido
            encrypted_content = self.encrypt_env_content(env_content)
            
            # Guardar archivo encriptado
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_content)
            
            logger.info(f"✅ Variables de entorno guardadas y encriptadas en {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error guardando archivo encriptado {file_path}: {str(e)}")
            return False

# Instancia global del encriptador
env_encryptor = EnvEncryption()
