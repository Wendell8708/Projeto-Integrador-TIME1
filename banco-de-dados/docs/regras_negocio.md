# Regras de Negócio

- Cada viagem possui um usuário responsável, uma fruta e um dispositivo.
- Cada medição e evento de impacto pertence a uma viagem e a um dispositivo.
- Os limites usados são copiados para a viagem para preservar o histórico.
- Umidade deve permanecer entre 0 e 100%.
- O fim da viagem não pode ser anterior ao início.
- Uma sequência de medição não pode se repetir para o mesmo dispositivo.
- Um código de evento de impacto não pode se repetir para o mesmo dispositivo.
- Todo alerta pertence a uma viagem e pode apontar para uma medição ou um evento de impacto.
- Cada viagem pode possuir no máximo uma inspeção final.
- A senha do Wi-Fi e strings de conexão não devem ser armazenadas no repositório.
