# CRTL-Lab — Controle de Acesso e Segurança para Laboratórios

## 1. Visão geral

O **CRTL-Lab** é um sistema de controle de acesso e monitoramento de segurança para laboratórios, desenvolvido como projeto acadêmico para a feira de Computação.

A proposta combina **visão computacional, inteligência artificial, sensores ambientais e automação** para auxiliar na prevenção e identificação de situações de risco em um laboratório.

O sistema utiliza duas câmeras — neste projeto, **smartphones funcionando como câmeras IP** — e um **Raspberry Pi 3B+** para integração com sensores e dispositivos de alerta.

As câmeras IP são analisadas diretamente pelo Raspberry Pi. O computador não executa os modelos: fica responsável pela interface gráfica, pela visualização dos streams e pelo histórico de eventos recebido via MQTT.

---

## 2. Objetivos

### Objetivo geral

Desenvolver um sistema capaz de verificar condições básicas de segurança no acesso e no ambiente de um laboratório, utilizando visão computacional e sensores para identificar situações inadequadas ou potencialmente perigosas.

### Objetivos específicos

- Detectar pessoas na entrada do laboratório.
- Verificar o uso dos principais equipamentos de proteção individual (EPIs).
- Identificar situações de EPI inadequado e gerar alertas.
- Monitorar o ambiente do laboratório por meio de uma segunda câmera.
- Detectar visualmente fumaça e possíveis sinais de incêndio.
- Integrar sensores ambientais ao sistema.
- Acionar LEDs, buzzer ou sirene em situações de alerta.
- Registrar eventos e ocorrências.
- Disponibilizar uma interface para acompanhamento do sistema.
- Demonstrar a integração entre inteligência artificial, software, sensores e sistemas embarcados.

---

## 3. Funcionalidades propostas

### 3.1 Controle de acesso

A primeira câmera ficará posicionada na região de entrada.

O sistema deverá:

1. Detectar a presença de uma pessoa.
2. Analisar a imagem.
3. Identificar os EPIs necessários.
4. Verificar se os requisitos de segurança foram atendidos.
5. Informar se o acesso está:
   - `PERMITIDO`
   - `ALERTA — EPI INADEQUADO`

Os itens inicialmente considerados são:

- Jaleco de manga comprida.
- Óculos de proteção.
- Calçado fechado.
- Cabelo devidamente preso, quando aplicável.

> O objetivo é verificar condições de segurança, e não identificar a identidade da pessoa. O projeto não depende de reconhecimento facial.

---

### 3.2 Monitoramento do laboratório

A segunda câmera será direcionada para o interior do laboratório.

Ela será utilizada para:

- Identificação visual de fumaça.
- Identificação visual de possíveis chamas/incêndios.
- Monitoramento contínuo do ambiente.
- Geração de eventos de alerta ou emergência.

---

### 3.3 Sensores ambientais

O Raspberry Pi 3B+ poderá receber dados de sensores como:

- Temperatura.
- Umidade.
- Gases.
- Partículas/fumaça, caso disponível.

Os sensores físicos complementam a visão computacional.

Uma câmera, por exemplo, não consegue detectar diretamente um gás invisível. Para isso, é necessário utilizar um sensor apropriado.

---

### 3.4 Sistema de alertas

Quando uma situação inadequada for detectada, o sistema poderá:

- Exibir um alerta no computador.
- Acender LEDs.
- Acionar um buzzer.
- Acionar uma sirene.
- Registrar o evento.
- Alterar o estado do sistema para `ALERTA` ou `EMERGÊNCIA`.

---

## 4. Arquitetura do sistema

```text
Smartphones ── stream IP ──► Raspberry Pi 3B+
                                  │ OpenCV DNN + YOLO ONNX
                                  │ Decisão + sensores + alarmes
                                  │
                                  └── MQTT ──► Computador (interface + SQLite)
       └──────── stream IP ─────────────────► Computador (visualização)
```

### Divisão das responsabilidades

**Smartphones**
- Captura de vídeo.
- Transmissão das imagens pela rede.

**Notebook/Computador**
- Interface gráfica e visualização dos streams IP.
- Recepção de status e eventos via MQTT.
- Histórico local de eventos em SQLite.

**Raspberry Pi 3B+**
- Captura dos streams IP e execução dos modelos de IA em CPU.
- Análise de EPIs e detecção visual de fumaça/incêndio.
- Leitura dos sensores.
- Controle de LEDs.
- Controle de buzzer/sirene.
- Decisão e acionamento local dos alertas, sem depender do computador.

---

## 5. Tecnologias previstas

### Software

- Python
- OpenCV DNN (inferência CPU no Raspberry)
- YOLOv8 exportado em ONNX
- MQTT
- SQLite
- FastAPI ou Flask
- HTML/CSS/JavaScript
- Git/GitHub

### Hardware

- Raspberry Pi 3B+
- Dois smartphones
- Sensores ambientais
- LEDs
- Resistores
- Buzzer
- Sirene, se disponível
- Botão de emergência/reset
- Fonte e componentes de prototipagem

---

## 6. Inteligência artificial

O projeto não pretende desenvolver uma rede neural do zero. O Raspberry executa um modelo YOLOv8 ONNX pequeno pelo OpenCV DNN, em CPU, com resolução e intervalo de inferência configuráveis.

Serão utilizadas bibliotecas e modelos existentes, principalmente:

- **OpenCV DNN** para inferência local com o modelo YOLOv8 ONNX.
- **Ultralytics**, opcional na máquina de desenvolvimento, para exportar modelos treinados.

Inicialmente poderão ser utilizados modelos pré-treinados para validar a infraestrutura.

Posteriormente, o modelo poderá ser ajustado com um conjunto de dados próprio para reconhecer os elementos específicos do projeto.

### Possíveis classes do modelo de EPI

```text
person
lab_coat
safety_glasses
closed_shoes
tied_hair
```

### Possíveis classes do modelo de emergência

```text
fire
smoke
```

A IA será responsável por responder:

> "O que aparece na imagem?"

Uma camada de software separada será responsável por responder:

> "O que essa detecção significa para a segurança do laboratório?"

Exemplo:

```text
Detecções:
- Jaleco: SIM
- Óculos: SIM
- Calçado fechado: NÃO
- Cabelo preso: SIM

Resultado:
ACESSO NEGADO
Motivo:
Calçado inadequado
```

---

## 7. Estados do sistema

O sistema poderá trabalhar com três estados principais:

```text
NORMAL
   │
   ├── EPI inadequado ──► ALERTA
   │                         │
   │                         └── EPI corrigido ──► NORMAL
   │
   └── Fumaça/Fogo/Gás ──► EMERGÊNCIA
```

### NORMAL

Nenhuma condição de risco identificada.

### ALERTA

Existe uma condição que exige atenção, mas não necessariamente uma emergência.

Exemplo:

- Pessoa sem óculos de proteção.
- Pessoa sem jaleco.

### EMERGÊNCIA

Existe uma situação potencialmente perigosa.

Exemplo:

- Incêndio.
- Grande quantidade de fumaça.
- Concentração perigosa de gás.
- Temperatura anormal, dependendo do sensor utilizado.

---

## 8. Registro de eventos

Os eventos poderão ser armazenados em um banco SQLite.

Exemplo:

| Data/Hora | Tipo | Descrição | Estado |
|---|---|---|---|
| 10:30 | EPI | Pessoa sem óculos | ALERTA |
| 10:42 | EPI | Acesso permitido | NORMAL |
| 11:05 | FUMAÇA | Fumaça detectada | EMERGÊNCIA |
| 11:06 | SENSOR | Temperatura elevada | EMERGÊNCIA |

Isso permitirá demonstrar o histórico de ocorrências durante a apresentação.

---

## 9. Estrutura inicial do projeto

```text
CRTL-Lab/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── cameras/
│   │   ├── entry_camera.py
│   │   └── lab_camera.py
│   │
│   ├── vision/
│   │   ├── person.py
│   │   ├── ppe.py
│   │   └── fire.py
│   │
│   ├── sensors/
│   │   ├── gas.py
│   │   ├── temperature.py
│   │   └── smoke.py
│   │
│   ├── safety/
│   │   ├── decision.py
│   │   └── alerts.py
│   │
│   ├── communication/
│   │   ├── mqtt_client.py
│   │   └── messages.py
│   │
│   ├── database/
│   │   └── database.py
│   │
│   └── web/
│       ├── app.py
│       ├── templates/
│       └── static/
│
├── models/
│   ├── ppe/
│   └── fire/
│
├── tests/
│
├── requirements.txt
├── PLANO_DESENVOLVIMENTO.md
└── README.md
```

Projeto do Raspberry:

```text
raspberry/
├── main.py
├── mqtt_client.py
│
├── sensors/
│   ├── gas.py
│   ├── temperature.py
│   └── smoke.py
│
└── actuators/
    ├── leds.py
    ├── buzzer.py
    └── siren.py
```

---

## 10. Resultado esperado

Ao final do projeto, espera-se obter um protótipo funcional capaz de:

1. Receber imagens de duas câmeras.
2. Detectar pessoas e elementos de segurança.
3. Avaliar o uso de EPIs.
4. Detectar visualmente fumaça/incêndio.
5. Receber informações de sensores.
6. Tomar decisões de segurança.
7. Comunicar-se com o Raspberry Pi.
8. Acionar dispositivos de alerta.
9. Registrar ocorrências.
10. Apresentar as informações em uma interface de monitoramento.

O principal diferencial do projeto está na **integração de diferentes tecnologias em um único sistema**, combinando visão computacional, inteligência artificial, sensores, sistemas embarcados, comunicação em rede e software de monitoramento.

---

## 11. Observação sobre segurança

O CRTL-Lab é um **protótipo acadêmico** e não deve ser considerado um sistema certificado de segurança ou substituto de equipamentos profissionais de prevenção e combate a incêndio.

Os sensores e modelos de inteligência artificial devem ser utilizados como mecanismos de demonstração e apoio à detecção de situações de risco.

---

## 12. Desenvolvimento inicial do Raspberry

A base do módulo Raspberry já foi iniciada no diretório `raspberry_pi/` com:

- leitura de sensores ambientais;
- gerenciamento de estados do sistema (`NORMAL`, `WARNING`, `ALERT`, `EMERGENCY`);
- controle de LEDs e buzzer/sirene em abstração de hardware;
- suporte a modo mock para testes sem hardware físico;
- preparação para comunicação MQTT com o computador central.

### Execução em modo mock

```bash
cd /home/filipe/Projects/CTRL-Lab
python3 raspberry_pi/main.py --mock --cycles 2
```

Esse comando valida a lógica do sistema e permite verificar a transição entre estados sem necessidade do Raspberry Pi real.

### Execução da visão no Raspberry Pi

O Pi deve alcançar os streams dos smartphones pela rede. Configure um broker MQTT no Pi (por exemplo, Mosquitto), mantenha as URLs IP das câmeras acessíveis e copie o modelo ONNX para o Raspberry.

Instale as dependências Python em um ambiente virtual no Raspberry:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Exemplo de execução no Pi com as duas câmeras:

```bash
python3 -m raspberry_pi.main \
  --broker localhost \
  --entry-camera http://192.168.0.10:8080/video \
  --lab-camera http://192.168.0.11:8080/video \
  --ai-model models/ctrlab-yolov8n.onnx \
  --ai-classes person,lab_coat,safety_glasses,closed_shoes,tied_hair,smoke,fire \
  --image-size 320 \
  --inference-interval 3
```

O modelo deve ser YOLOv8 em ONNX com saída sem NMS no formato `[1, 4 + número_de_classes, candidatos]`. Os nomes e a ordem de `--ai-classes` precisam corresponder exatamente às classes usadas no treinamento. Um modelo COCO genérico não reconhece automaticamente jaleco, óculos, calçados, cabelo preso, fumaça ou fogo: use um modelo treinado para essas classes. Para exportar, em uma máquina de desenvolvimento com Ultralytics instalado:

```bash
yolo export model=best.pt format=onnx imgsz=320
```

O Pi não precisa instalar PyTorch ou Ultralytics para executar o modelo. Estados e detecções são publicados no tópico `ctrlab/raspberry/status`; o computador pode consumi-los para a interface e o histórico sem executar inferência. A interface gráfica em si continua sendo uma etapa pendente.

---

## 13. Fase 1 — Testar a primeira câmera IP

A primeira implementação de aquisição de vídeo foi criada em [app/cameras/entry_camera.py](app/cameras/entry_camera.py), com suporte a:

- stream IP do smartphone em HTTP/RTSP;
- câmera local do computador;
- configuração inicial de largura, altura e FPS;
- leitura de frames com OpenCV.

Exemplo de uso:

```python
from app.cameras.entry_camera import CameraConfig, StreamCamera

camera = StreamCamera(
    CameraConfig(
        name="entry",
        url="http://192.168.0.10:8080/video",
        width=1280,
        height=720,
        fps=30,
    )
)

camera.open()
frame = camera.read_frame()
print(frame is not None)
camera.close()
```

Esse módulo pode ser usado pela interface gráfica para exibir diretamente o stream do smartphone. A mesma URL é consumida pelo Raspberry para inferência; o computador não processa os frames.
