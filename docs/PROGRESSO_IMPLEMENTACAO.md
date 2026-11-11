# Progresso de implementação do CTRL-Lab

## Visão geral

Este documento registra o que foi implementado até o momento no projeto, com foco na arquitetura funcional do sistema e nos módulos já desenvolvidos.

Para o escopo atual da apresentação, a inferência pode ser iniciada somente com o modelo pessoa/jaleco; a avaliação de visão exige jaleco, sem exigir calça, calçado ou cabelo. O modelo visual de fogo/fumaça permanece opcional. Sensores físicos configurados no runtime continuam independentes. Para detalhes atuais e pendências de hardware/modelos, consulte [FUNCIONAMENTO_ATUAL.md](./FUNCIONAMENTO_ATUAL.md) e [PENDENCIAS_CONCLUSAO.md](./PENDENCIAS_CONCLUSAO.md).

## 1. Estrutura do projeto atual

```text
CTRL-Lab/
├── app/
│   ├── __init__.py
│   └── cameras/
│       ├── __init__.py
│       └── entry_camera.py
│
├── central/
│   ├── __init__.py
│   ├── events.py
│   ├── dashboard.py
│   ├── dashboard.html
│   └── mqtt_listener.py
│
├── raspberry_pi/
│   ├── __init__.py
│   ├── alerts.py
│   ├── config.py
│   ├── hardware.py
│   ├── main.py
│   ├── camera_stream.py
│   ├── keyboard.py
│   ├── mqtt_client.py
│   ├── sensors.py
│   └── vision.py
│
├── tests/
│   ├── test_central_events.py
│   ├── test_central_mqtt.py
│   ├── test_camera_stream.py
│   ├── test_dashboard.py
│   ├── test_entry_camera.py
│   ├── test_raspberry_core.py
│   ├── test_raspberry_vision.py
│   ├── test_yolo_base.py
│   └── test_yolo_onnx.py
│
├── docs/
│   ├── README.md
│   └── PROGRESSO_IMPLEMENTACAO.md
│
├── .gitignore
├── PLANO_DESENVOLVIMENTO.md
├── README.md
├── requirements.txt
└── ...
```

## 2. Implementações concluídas

### 2.1 Módulo Raspberry Pi

O Raspberry concentra a execução e as decisões de visão, além das tarefas embarcadas:

- leitura de temperatura e umidade por DHT22 opcional;
- leitura digital do limiar DO do MQ-2 (sem cálculo de ppm);
- botão de emergência com contato mecanicamente travado e botão separado de reset; câmera/visão e saídas são pausadas durante emergência, enquanto sensores, botões e MQTT/status permanecem ativos; o reset aguarda uma inferência visual segura e riscos críticos ausentes;
- teste de captura da PS3 Eye por CLI sem exigir modelos ONNX;
- valores simulados de sensores somente quando executado com `--mock`;
- publicação como indisponíveis dos sensores físicos que não estão conectados/implementados;
- estados do sistema: NORMAL, WARNING, ALERT e EMERGENCY;
- controle do buzzer via abstração de hardware, acionado somente em EMERGENCY; LEDs e sirene não são usados;
- compatibilidade com modo mock para execução sem Raspberry real;
- comunicação base para MQTT;
- inferência CPU com OpenCV DNN e YOLOv8 ONNX, sem PyTorch no Pi;
- captura de uma câmera USB; a captura para inferência usa worker, enquanto a pré-visualização sem IA captura/codifica no loop cooperativo;
- controle em execução do modelo de acesso por MQTT e pelo atalho `A` no terminal;
- publicação dos resultados visuais junto ao status MQTT;
- acionamento local de ALERTA/EMERGÊNCIA por EPI inadequado ou fogo/fumaça.

Arquivos principais:

- [raspberry_pi/config.py](../raspberry_pi/config.py)
- [raspberry_pi/sensors.py](../raspberry_pi/sensors.py)
- [raspberry_pi/alerts.py](../raspberry_pi/alerts.py)
- [raspberry_pi/hardware.py](../raspberry_pi/hardware.py)
- [raspberry_pi/main.py](../raspberry_pi/main.py)
- [raspberry_pi/keyboard.py](../raspberry_pi/keyboard.py)
- [raspberry_pi/mqtt_client.py](../raspberry_pi/mqtt_client.py)
- [raspberry_pi/vision.py](../raspberry_pi/vision.py)

### 2.2 Sistema central

Foi iniciada a base da aplicação central para receber os dados do Raspberry e registrar eventos:

- armazenamento em SQLite;
- criação de eventos a partir do payload recebido;
- classificação dos eventos por tipo e estado;
- listener MQTT pronto para receber as mensagens do Raspberry.
- método para comandar o estado do modelo de acesso pelo tópico central.
- dashboard web com estado MQTT, sensores, eventos recentes e comando remoto protegido por token.
- pré-visualização MJPEG protegida da câmera no dashboard, sem abrir uma segunda captura.

Arquivos principais:

- [central/events.py](../central/events.py)
- [central/dashboard.py](../central/dashboard.py)
- [central/dashboard.html](../central/dashboard.html)
- [central/mqtt_listener.py](../central/mqtt_listener.py)
- [central/__init__.py](../central/__init__.py)

### 2.3 Módulo de câmeras

Foi criada a infraestrutura para aquisição de vídeo das câmeras:

- uma única captura local da PS3 Eye;
- compartilhamento do mesmo frame entre o modelo contínuo de segurança e o modelo de acesso alternável;
- o runtime não abre duas câmeras nem depende de stream IP de celular.
- servidor MJPEG transmite frames recentes capturados pelo mesmo ciclo da câmera.

Arquivos principais:

- [app/cameras/entry_camera.py](../app/cameras/entry_camera.py)

### 2.4 Visão computacional

O projeto agora conta com duas opções de detector:

- wrapper existente de Ultralytics, útil na máquina de desenvolvimento;
- OpenCV DNN para inferência de YOLOv8 ONNX em CPU no Raspberry;
- modelo de segurança (fumaça/fogo) sempre executado;
- modelo de acesso/EPI opcional, desabilitado por padrão, carregado sob demanda e liberado da memória ao desativar.

O dashboard está disponível em `central/dashboard.py` e sua integração usa `CentralMQTTListener.set_access_model_enabled(enabled)`, que publica o comando no tópico MQTT `ctrlab/central/commands`. O controle recebe confirmação de estado em `vision.access.enabled` dentro do status publicado.

O repositório não contém pesos. Para a demonstração atual, forneça um ONNX YOLOv8 treinado para `person` e `lab_coat`; a caixa de jaleco é associada à caixa da pessoa. O detector visual opcional de fogo/fumaça pode usar um modelo separado com classes `smoke` e `fire`. Outros requisitos de EPI não fazem parte do escopo atual da demonstração.

Arquivos principais:

- [app/vision/yolo_base.py](../app/vision/yolo_base.py)
- [app/vision/yolo_onnx.py](../app/vision/yolo_onnx.py)
- [raspberry_pi/vision.py](../raspberry_pi/vision.py)
- [app/vision/__init__.py](../app/vision/__init__.py)

## 3. Testes implementados

O projeto já conta com testes iniciais para os módulos principais:

- teste do sistema central de eventos;
- teste do stream MJPEG protegido e do proxy do dashboard;
- teste da câmera de entrada;
- testes da câmera e do frame compartilhado pelos dois modelos;
- teste do Raspberry em estados e payloads;
- testes de ausência de leituras físicas e de valores simulados;
- teste da base do detector YOLO;
- teste de decodificação ONNX e execução CPU;
- teste do pipeline visual de EPI e fumaça/fogo.

Arquivos de teste:

- [tests/test_central_events.py](../tests/test_central_events.py)
- [tests/test_central_mqtt.py](../tests/test_central_mqtt.py)
- [tests/test_dashboard.py](../tests/test_dashboard.py)
- [tests/test_entry_camera.py](../tests/test_entry_camera.py)
- [tests/test_raspberry_core.py](../tests/test_raspberry_core.py)
- [tests/test_raspberry_camera_test.py](../tests/test_raspberry_camera_test.py)
- [tests/test_raspberry_hardware.py](../tests/test_raspberry_hardware.py)
- [tests/test_raspberry_sensors.py](../tests/test_raspberry_sensors.py)
- [tests/test_raspberry_vision.py](../tests/test_raspberry_vision.py)
- [tests/test_yolo_base.py](../tests/test_yolo_base.py)
- [tests/test_yolo_onnx.py](../tests/test_yolo_onnx.py)

## 4. Próximos passos sugeridos

1. Treinar/exportar e validar os dois pesos ONNX para as classes específicas.
2. Instalar e configurar um broker MQTT no Raspberry e validar os comandos reais.
3. Validar o dashboard e comandos em uma rede com Raspberry e broker reais.
4. Medir FPS/CPU/RAM e estabilidade com a PS3 Eye e o modelo pessoa/jaleco no Raspberry.
5. Validar o stream MJPEG e a taxa de quadros com a PS3 Eye no Raspberry real.

## 5. Observação

A base do projeto está organizada para dar continuidade ao desenvolvimento em etapas, seguindo a ordem definida em [PLANO_DESENVOLVIMENTO.md](../PLANO_DESENVOLVIMENTO.md).

No modo real, o DHT22 só fornece leituras se a biblioteca e o sensor estiverem disponíveis. O MQ-2 fornece somente o estado digital do comparador; não há medição em ppm. Confirme tensão e polaridade do pino DO do módulo. Os arquivos ONNX também não estão no repositório, então inferência com câmera real depende do fornecimento dos pesos.
