#!/usr/bin/env python
"""Voice Manager - Transcripción y síntesis de voz"""
from faster_whisper import WhisperModel
from gtts import gTTS
import os
import shutil

# Rutas
WORKSPACE = 'C:/Users/omimz/.nanobot/workspace'
VOICE_INPUT = 'C:/contenedores/compose/voice/input'
VOICE_OUTPUT = 'C:/Users/omimz/.nanobot/workspace'

# Modelos Whisper
WHISPER_MODEL = 'base'

def transcribe_audio(audio_path):
    """
    Transcribe audio a texto usando Faster-Whisper
    """
    print(f'Transcribiendo: {audio_path}')
    model = WhisperModel(WHISPER_MODEL, device='cpu', compute_type='int8')
    segments, info = model.transcribe(audio_path, language='es')
    
    text = ''
    for segment in segments:
        text += segment.text + ' '
    
    return text.strip()

def speak(text, output_file='respuesta.mp3'):
    """
    Convierte texto a voz usando gTTS
    Guarda en la carpeta workspace para poder enviar por Telegram
    """
    print(f'Generando audio: {text[:50]}...')
    tts = gTTS(text, lang='es')
    
    # Guardar en workspace
    output_path = os.path.join(VOICE_OUTPUT, output_file)
    tts.save(output_path)
    
    print(f'Audio guardado: {output_path}')
    return output_path

def main():
    import sys
    
    if len(sys.argv) < 2:
        print('Uso: python voice_manager.py <audio_file>')
        print('O para generar voz: python voice_manager.py --speak "texto"')
        return
    
    if sys.argv[1] == '--speak':
        text = ' '.join(sys.argv[2:])
        path = speak(text)
        print(f'Listo: {path}')
    else:
        audio_file = sys.argv[1]
        if not os.path.exists(audio_file):
            print(f'Archivo no encontrado: {audio_file}')
            return
        text = transcribe_audio(audio_file)
        print(f'TEXTO: {text}')

if __name__ == '__main__':
    main()
