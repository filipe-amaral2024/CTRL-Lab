# Materiais, apps e plano de montagem do CTRL-Lab

## 1. Aplicativos para transformar o celular em câmera IP

### Recomendação principal

#### Android: IP Webcam
- Funciona bem para stream em rede local.
- Gera URL de vídeo fácil de usar no OpenCV.
- Boa opção para protótipo acadêmico.
- Exemplo de URL típica:
  - http://192.168.0.10:8080/video

#### iPhone: Camo
- Boa alternativa para iPhone.
- Também funciona como câmera IP pela rede local.
- Útil quando o notebook e o celular estiverem na mesma Wi‑Fi.

### Alternativa

#### DroidCam
- Funciona bem e é simples de configurar.
- Bom para quem quer algo mais direto em ambiente de laboratório.

### Regras práticas

- Conectar celular e notebook na mesma rede Wi‑Fi.
- Verificar a URL de stream antes de começar a integração.
- Testar a estabilidade antes de conectar à lógica do sistema.

---

## 2. Lista de materiais recomendados

### 2.1 Raspberry Pi

- Raspberry Pi 3B+ ou 4
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
Celular 1 (entrada) ── Wi‑Fi ── Notebook
Celular 2 (laboratório) ── Wi‑Fi ── Notebook

Notebook:
- OpenCV
- YOLO
- lógica de EPI
- visão para fumaça/incêndio
- comunicação MQTT

Raspberry Pi:
- DHT22
- MQ-2/MQ-135
- LEDs
- buzzer
- botão de emergência
- status via MQTT
```

---

## 6. Ordem recomendada de montagem

1. Montar Raspberry com LEDs e buzzer.
2. Validar GPIO e estado visual do sistema.
3. Integrar DHT22 e testar temperatura/umidade.
4. Integrar sensor de gás e validar leitura.
5. Conectar botão de emergência.
6. Validar comunicação MQTT.
7. Conectar câmeras e testar streams.
8. Adicionar lógica de IA e segurança.

---

## 7. Dicas de projeto para apresentação

- Use dois celulares, um para entrada e um para laboratório.
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

- [ ] celulares conectados na mesma rede Wi‑Fi
- [ ] URLs do stream funcionando
- [ ] notebook recebendo os vídeos
- [ ] Raspberry lendo sensores
- [ ] LEDs funcionando
- [ ] buzzer funcionando
- [ ] MQTT funcionando
- [ ] lógica de risco validada
- [ ] apresentação preparada com cenários reais

---

## 9. Recomendação final

Para reduzir riscos e aumentar a chance de funcionar bem, a melhor opção é:

- usar celular Android + IP Webcam
- montar protótipo com LEDs + DHT22 + MQ-2 + buzzer
- validar primeiro a parte eletrônica e de comunicação
- depois avançar para a parte de IA e câmera

Esse caminho é simples, barato e bem adequado ao escopo acadêmico do projeto.
