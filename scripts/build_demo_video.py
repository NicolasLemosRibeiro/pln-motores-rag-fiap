"""Gera um video narrado de 3–5 minutos com os resultados reais do projeto."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "outputs" / "_video_assets"
VIDEO = ROOT / "docs" / "demo_assistente_pln.mp4"
FONT_REG = Path("C:/Windows/Fonts/segoeui.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/seguisb.ttf")
NAVY = "#0B2545"
BLUE = "#2E74B5"
LIGHT = "#F2F4F7"
GOLD = "#C69214"
GREEN = "#4E8B3A"


def wrapped_lines(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines


def make_slide(index, title, bullets, accent=BLUE):
    image = Image.new("RGB", (1920, 1080), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(str(FONT_BOLD), 62)
    body_font = ImageFont.truetype(str(FONT_REG), 38)
    small_font = ImageFont.truetype(str(FONT_REG), 25)
    draw.rectangle((0, 0, 1920, 20), fill=accent)
    draw.text((110, 78), title, font=title_font, fill=NAVY)
    draw.line((110, 170, 1810, 170), fill=accent, width=4)
    y = 235
    for bullet in bullets:
        lines = wrapped_lines(draw, bullet, body_font, 1510)
        draw.ellipse((125, y + 16, 145, y + 36), fill=accent)
        for j, line in enumerate(lines):
            draw.text((175, y + j * 55), line, font=body_font, fill=NAVY)
        y += len(lines) * 55 + 52
    draw.rounded_rectangle((110, 955, 1810, 1010), radius=18, fill=LIGHT)
    draw.text((140, 967), "PLN Industrial | Sprints 3 e 4 | Dados sintéticos", font=small_font, fill="#667085")
    draw.text((1710, 967), f"{index}/9", font=small_font, fill="#667085")
    path = ASSETS / f"slide-{index:02d}.png"
    image.save(path)
    return path


def synthesize(text, path):
    safe_text = text.replace("'", "''")
    safe_path = str(path).replace("'", "''")
    script = f"""Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Maria Desktop')
$s.Rate = 3
$s.Volume = 100
$s.SetOutputToWaveFile('{safe_path}')
$s.Speak('{safe_text}')
$s.Dispose()
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded], check=True, capture_output=True)


def main():
    if ASSETS.exists(): shutil.rmtree(ASSETS)
    ASSETS.mkdir(parents=True)
    m3 = json.loads((ROOT / "outputs" / "metricas_sprint3.json").read_text(encoding="utf-8"))
    m4 = json.loads((ROOT / "outputs" / "metricas_sprint4.json").read_text(encoding="utf-8"))
    demo = json.loads((ROOT / "outputs" / "demonstracao_cenarios.json").read_text(encoding="utf-8"))

    slides = [
        ("PLN para alertas e troubleshooting", [
            "Uma solução integrada para transformar sinais numéricos em linguagem acessível.",
            "RAG sobre documentação técnica com contexto operacional real do ativo.",
            "Demonstração reproduzível, offline e rastreável.",
        ], "Neste vídeo eu apresento a solução integrada das Sprints três e quatro. Primeiro, sinais numéricos de sensores são convertidos em alertas técnicos compreensíveis. Depois, o mesmo contexto operacional alimenta um assistente de troubleshooting fundamentado em documentos. A demonstração usa dados e manuais sintéticos, roda de forma reproduzível e não depende de uma API paga."),
        ("Sprint 3: alertas e classificação", [
            "30 alertas: níveis leve, moderado e crítico.",
            "200 eventos em cinco categorias operacionais.",
            f"Macro F1: {m3['classificacao']['macro_f1']:.3f} no holdout sintético.",
            f"ROUGE-1: {m3['rouge']['rouge1']:.3f} | ROUGE-L: {m3['rouge']['rougeL']:.3f}.",
        ], "Na Sprint três, cada alerta preserva equipamento, sensor, magnitude, baseline, janela e horário. O tom muda conforme a urgência: o nível leve orienta acompanhamento, o moderado pede inspeção direcionada e o crítico explicita risco e parada segura. O classificador separa manutenção corretiva, preventiva, anomalia elétrica, mecânica e operação normal. O F um perfeito deve ser interpretado com cautela, pois o conjunto é sintético e balanceado. ROUGE compara as narrativas com referências manuais, e um checklist verifica clareza, precisão, utilidade e rastreabilidade."),
        ("Relatório operacional rastreável", [
            "Alertas emitidos e equipamentos em risco.",
            "Tendências por tipo de sensor.",
            "Recomendações preliminares.",
            "Cada afirmação cita alerta, sensor, valor e timestamp.",
        ], "O relatório diário ou semanal resume alertas, equipamentos em risco, tendências e recomendações preliminares. A rastreabilidade é obrigatória: cada afirmação factual aponta alerta, sensor, valor e timestamp. Assim, o operador consegue voltar ao dado que originou a narrativa. As recomendações são apoio à decisão e não substituem procedimentos de segurança ou diagnóstico em campo."),
        ("Arquitetura RAG", [
            "Chunking por cabeçalhos e parágrafos técnicos.",
            "Embeddings TF-IDF offline ou Sentence Transformers.",
            "Índice vetorial NearestNeighbors ou FAISS.",
            "Re-ranking por pergunta, seção, anomalia e severidade.",
        ], "Na Sprint quatro, os documentos são divididos por cabeçalhos e parágrafos, preservando a coerência de cada procedimento. A execução offline usa embeddings TF IDF e índice vetorial por cosseno. No Colab, é possível ativar Sentence Transformers e FAISS. O re-ranking combina similaridade do conteúdo, similaridade do cabeçalho, cobertura lexical e bônus de metadados. O tipo de anomalia, o equipamento, o sensor e a severidade ajudam a priorizar o trecho mais útil para a situação atual."),
        ("Cenário 1: anomalia elétrica", [
            "Pergunta: corrente desequilibrada — o que verificar?",
            "Recuperação: Desequilíbrio de corrente entre fases.",
            "Ação: medir as três fases e revisar conexões desenergizadas.",
            "Fonte e confiança aparecem na resposta.",
        ], "No primeiro cenário, o alerta informa desequilíbrio de corrente no Motor MT zero quarenta e dois. O assistente recupera a seção sobre corrente entre fases. A resposta orienta registrar corrente e tensão nas três fases, avaliar alimentação e carga e, com o equipamento desenergizado e bloqueado, verificar bornes, torque, aquecimento e continuidade. A fonte é citada como manual do motor, seção desequilíbrio de corrente, e a confiança é apresentada com justificativa."),
        ("Cenário 2: anomalia mecânica", [
            "Alerta crítico: vibração de 8,1 mm/s RMS e ruído metálico.",
            "Recuperação: Vibração elevada no mancal.",
            "Prioridade: parada segura e inspeção do conjunto.",
            "Contexto crítico altera a urgência da resposta.",
        ], "No cenário mecânico, a vibração atingiu oito vírgula um milímetros por segundo RMS e surgiu ruído metálico. Como o contexto é crítico, o retriever prioriza vibração elevada no mancal e também considera instruções de parada segura. A resposta recomenda inspecionar fixações, base, acoplamento e condição do mancal. O texto não autoriza intervenção energizada e deixa claro que o crescimento rápido combinado com ruído ou temperatura alta exige parada segura."),
        ("Cenário 3: manutenção preventiva", [
            "Pergunta: quais verificações executar no trimestre?",
            "Ventilação, conexões, acoplamento, alinhamento e base.",
            "Revisão de corrente, temperatura e vibração.",
            "Memória curta mantém até quatro turnos.",
        ], "No terceiro cenário, o operador pergunta sobre a manutenção trimestral. A resposta recupera a rotina preventiva e lista limpeza da ventilação, torque das conexões, inspeção do acoplamento, alinhamento, base e revisão das tendências de corrente, temperatura e vibração. Quando previsto, a caixa de ligação e a resistência de isolamento são verificadas com o motor desenergizado. A memória curta conserva os quatro últimos turnos para perguntas de continuação sem carregar contexto indefinidamente."),
        ("Avaliação e limites", [
            f"Precision@1: {m4['retrieval']['precision_at_1']:.3f} | Hit@4: {m4['retrieval']['hit_at_k']:.3f}.",
            f"Faithfulness: {m4['assistant']['faithfulness']:.3f} | Relevancy: {m4['assistant']['answer_relevancy']:.3f}.",
            "20 perguntas com gabarito documental.",
            "Abstenção para valores ou ativos fora do corpus.",
        ], "A avaliação contém vinte perguntas com respostas e seções de referência. O retriever atingiu precisão na primeira posição de zero vírgula oitenta e cinco, acerto entre os quatro primeiros de um vírgula zero e M R R de zero vírgula novecentos e dezessete. Faithfulness e relevância são proxies locais transparentes, que devem ser complementadas por avaliação humana e RAGAS. O sistema deve se abster em perguntas fora do corpus, não inventar torque ou limite e nunca substituir engenharia, segurança ou manual do fabricante."),
        ("Entrega pronta para reprodução", [
            "Dois notebooks Colab executados sem erros.",
            "Dados, gabaritos, outputs, testes e documentação.",
            "Relatório final unificado com nove páginas.",
            "Próximo passo: validar com dados e especialistas reais.",
        ], "A pasta final contém os dois notebooks executados, dados de alertas e eventos, vinte perguntas, três documentos técnicos, outputs detalhados, testes, relatório unificado e este vídeo. A prova de conceito demonstra o fluxo completo, mas a passagem para produção exige documentos reais versionados, rótulos de campo, validação por especialistas, testes adversariais, controle de acesso e aprovação humana obrigatória. Obrigado."),
    ]

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    segments = []
    for i, (title, bullets, narration) in enumerate(slides, start=1):
        image = make_slide(i, title, bullets, BLUE if i not in {5, 6, 8} else (GOLD if i == 5 else GREEN if i == 6 else "#9B1C1C"))
        audio = ASSETS / f"audio-{i:02d}.wav"
        segment = ASSETS / f"segment-{i:02d}.mp4"
        synthesize(narration, audio)
        subprocess.run([
            ffmpeg, "-y", "-loop", "1", "-framerate", "30", "-i", str(image), "-i", str(audio),
            "-filter_complex", "[1:a]volume=1.35,apad=pad_dur=1.0[a]", "-map", "0:v", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-c:a", "aac",
            "-b:a", "160k", "-pix_fmt", "yuv420p", "-shortest", str(segment),
        ], check=True, capture_output=True)
        segments.append(segment)

    concat = ASSETS / "concat.txt"
    concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in segments), encoding="utf-8")
    subprocess.run([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c", "copy", "-movflags", "+faststart", str(VIDEO),
    ], check=True, capture_output=True)
    print(VIDEO)


if __name__ == "__main__":
    main()
