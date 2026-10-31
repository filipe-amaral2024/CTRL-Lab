# Materiais e plano de montagem do CTRL-Lab

## 1. Câmera do projeto

O projeto utilizará somente uma **PS3 Eye conectada por USB ao Raspberry Pi**. Ela fornece cada frame aos dois modelos de IA: o modelo de segurança, que fica sempre ativo, e o modelo de acesso/EPI, que pode ser alternado durante a execução.

A câmera de celular via IP foi descartada por apresentar latência e travamentos. Não é necessário instalar aplicativo de streaming nem manter os celulares na rede para a captura.

---

## 2. Lista de materiais recomendados

### 2.1 Raspberry Pi

- Raspberry Pi 3B+ ou 4
- Câmera PS3 Eye USB
- MicroSD 32 GB
- Fonte 5V 3A
- Case do Raspberry
- Cabo microSD
- Cabo HDMI opcional
- Teclado e mouse opcionais

### 2.2 Componentes eletrônicos básicos

- Protoboard
- Jumpers macho-fêmea e fêmea-fêmea
- Resistores 220 Ω (3 unidades no mínimo)
- LEDs vermelho, amarelo e verde
- Buzzer
- DHT22 (temperatura e umidade)
- Sensor MQ-2 ou MQ-135 (gás/fumaça)
- Botão de emergência
- Fios de conexão

### 2.3 Componentes opcionais

- Sirene de 12V
- Relé ou transistor para sirene
- Módulo ADC para sensor analógico
- Fonte dedicada para sirene/atuadores mais potentes

---

## 3. Materiais mínimos para protótipo funcional

Se a intenção for começar com um protótipo simples e funcional, a lista mínima é:

- 1 Raspberry Pi 3B+
- 1 câmera PS3 Eye USB
- 1 microSD 32 GB
- 1 fonte 5V 3A
- 1 breadboard
- 3 LEDs
- 3 resistores 220 Ω
- 1 buzzer
- 1 DHT22
- 1 sensor MQ-2
- 1 botão de emergência
- jumpers

Essa configuração já permite validar:

- monitoramento ambiental
- lógica de alertas
- comunicação com o computador central
- acionamento de indicadores visuais e sonoros

---

## 4. Plano de montagem recomendando para o protótipo

### Etapa 1 — Montar alimentação e referência

- Conectar Raspberry Pi à fonte correta.
- Conectar protoboard ao GND e à alimentação 5V.
- Garantir que a massa comum esteja organizada.

### Etapa 2 — Montar LEDs indicativos

- LED vermelho -> GPIO22 -> resistor 220 Ω -> GND
- LED amarelo -> GPIO27 -> resistor 220 Ω -> GND
- LED verde -> GPIO24 -> resistor 220 Ω -> GND

Essa é a base visual do sistema para indicar:

- NORMAL — verde
- ALERTA — amarelo
- EMERGÊNCIA — vermelho

### Etapa 3 — Montar buzzer

- Buzzer -> GPIO23
- Em alguns casos, usar transistor ou módulo driver para garantir melhor desempenho.

### Etapa 4 — Montar o DHT22

- VCC -> alimentação adequada do sensor
- GND -> GND
- DATA -> GPIO17

Esse sensor permite medir:

- temperatura
- umidade

### Etapa 5 — Montar o sensor de gás

- MQ-2 ou MQ-135 conforme disponibilidade
- VCC -> 5V
- GND -> GND
- OUT -> entrada analógica ou digital conforme módulo

### Etapa 6 — Botão de emergência

- Botão ligado com pull-up ou pull-down
- Conectar a GPIO de entrada
- Usado para simular parada de emergência ou reset manual

---

## 5. Estrutura lógica da montagem

```text
PS3 Eye (USB) ── Raspberry Pi (captura de frame + dois modelos)
                           │
                           └── MQTT ── Computador (interface/histórico)

Computador:
- Dashboard futuro; alterna somente o modelo de acesso via MQTT
- Recepção de eventos via MQTT
- Histórico SQLite

Raspberry Pi:
- Uma captura por ciclo da PS3 Eye
- Modelo de segurança (fumaça/fogo) sempre ativo
- Modelo de acesso/EPI somente quando habilitado
- DHT22
- MQ-2/MQ-135
- LEDs
- buzzer
- botão de emergência
- status e eventos via MQTT
```

---

### Execução do modelo no Pi

Conecte a PS3 Eye ao Pi e confirme o índice de dispositivo (padrão `0`). Copie os modelos ONNX para o Pi. Instale apenas as dependências Python de [requirements.txt](../requirements.txt); não é necessário instalar Ultralytics nem PyTorch para inferência. Ultralytics pode ser usado em outro computador apenas para exportar os modelos YOLOv8 em ONNX com `imgsz=320`.

Exemplo:

```bash
python3 -m raspberry_pi.main \
  --broker localhost \
  --camera-device 0 \
  --safety-model models/ctrlab-safety.onnx \
  --access-model models/ctrlab-access.onnx \
  --safety-classes smoke,fire \
  --access-classes person,lab_coat,safety_glasses,closed_shoes,tied_hair
```

O modelo de acesso inicia desabilitado, é carregado sob demanda e liberado da memória quando desativado. Pressione `A` no terminal ou use o botão do dashboard para alterná-lo. O comando usa o tópico `ctrlab/central/commands`; desabilitar o acesso não desliga a análise contínua de segurança. Os modelos devem conter suas classes na ordem configurada e gerar saída YOLOv8 sem NMS suportada pelo OpenCV DNN. O projeto fornece o runtime e a lógica, mas não inclui os pesos treinados. O MQTT publica resultados e o estado de ativação no tópico `ctrlab/raspberry/status`.

### Acesso ao dashboard pela rede local

Execute o dashboard no computador que receberá os status MQTT. No PowerShell:

```powershell
pip install -r requirements.txt
$env:CTRL_LAB_DASHBOARD_TOKEN = "use-um-token-aleatorio-com-16-caracteres-ou-mais"
python -m central.dashboard --host 0.0.0.0 --port 8000 --broker <IP_DO_RASPBERRY>
```

No navegador de qualquer dispositivo na mesma rede, abra `http://<IP_DO_COMPUTADOR>:8000` e informe o token. O dashboard mostra estado, sensores, resultados da visão e eventos recentes. O botão remoto apenas alterna o modelo de acesso; não desliga a análise contínua de segurança. O status é atualizado via MQTT. O vídeo da PS3 Eye não é transmitido pelo dashboard.

Libere a porta TCP 8000 no firewall do computador anfitrião para a rede local e garanta que o broker MQTT no Raspberry aceite conexões dessa rede. Não exponha o dashboard ou o broker diretamente à Internet: a interface usa HTTP sem criptografia e deve permanecer em uma rede confiável.

## 6. Ordem recomendada de montagem

1. Montar Raspberry com LEDs e buzzer.
2. Validar GPIO e estado visual do sistema.
3. Integrar DHT22 e testar temperatura/umidade.
4. Integrar sensor de gás e validar leitura.
5. Conectar botão de emergência.
6. Validar comunicação MQTT.
7. Conectar a PS3 Eye e validar a captura local.
8. Copiar os dois modelos ONNX e validar a segurança contínua e a alternância do acesso.
9. Configurar o broker, iniciar o dashboard web e conectar status/comandos MQTT.

---

## 7. Dicas de projeto para apresentação

- Use a PS3 Eye fixa, enquadrando a área de acesso e a área que precisa de monitoramento de segurança.
- Confirme que desligar o modelo de acesso não interrompe o modelo de segurança.
- Faça a montagem em protoboard, fácil de demonstrar.
- Use LEDs e buzzer para deixar a lógica visualmente clara.
- Mostre a transição entre NORMAL, ALERTA e EMERGÊNCIA.
- Simule cenários como:
  - pessoa sem jaleco
  - fumaça detectada
  - temperatura alta
  - gás acima do limite

---

## 8. Checklist final antes da apresentação

- [ ] PS3 Eye detectada e estável no Raspberry Pi
- [ ] modelo de segurança executando continuamente
- [ ] atalho `A` alternando o modelo de acesso
- [ ] comando MQTT alternando o modelo de acesso
- [ ] Raspberry lendo sensores
- [ ] LEDs funcionando
- [ ] buzzer funcionando
- [ ] MQTT funcionando
- [ ] dashboard acessível pelo IP do computador anfitrião
- [ ] token configurado e controle remoto de acesso validado
- [ ] lógica de risco validada
- [ ] apresentação preparada com cenários reais

---

## 9. Recomendação final

Para reduzir latência e consumo de recursos:

- usar somente uma câmera PS3 Eye USB para os dois modelos
- manter a inferência do modelo de acesso desligada quando não for necessária
- montar protótipo com LEDs + DHT22 + MQ-2 + buzzer
- validar primeiro a parte eletrônica e de comunicação
- medir desempenho dos modelos na resolução configurada

Esse caminho é simples, barato e bem adequado ao escopo acadêmico do projeto.
