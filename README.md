# The Evolution of Sacrificing

> A simulation of the **Alarm Call Game** exploring how altruistic self-sacrifice traits can evolve and survive in a hostile environment.

## 🦁 The Game Mechanics

This simulation extends the classic **Alarm Call Game** with advanced social features:

1.  **Reputation System**: Every agent has a social credit score (`-2` to `+3`). Actions (Notify/Run) directly impact reputation, and reputation influences how others treat you.
2.  **Noise & Misunderstanding**: Communication isn't perfect (`1%` failure rate). A hero might be mistaken for a coward, testing the society's forgiveness.
3.  **Migration**: Agents can move to empty spots (`10%` chance), simulating refugees and urbanization.
4.  **Cultural Transmission**: Agents can be influenced by successful neighbors (`5%` chance), leading to conversion (enlightenment) or corruption.

## 🧠 Strategies

The ecosystem has evolved into a class struggle:

* **😇 Altruist**: The saint. Helps everyone, fuels the reputation economy.
* **😈 Cheater / Xenophobe**: The selfish base. Exploits or isolates.
* **🎩 Politician**: The manipulator. Farms reputation from the weak to exploit the elite.
* **🔮 Prophet**: The forgiving leader. Saves anyone with high reputation, stabilizing society.
* **⚖️ Sheriff**: The enforcer. Punishes bad behavior regardless of reputation.
* **🔨 Simpleton / Jacobin**: The reactionaries. Anti-elite or pure tit-for-tat.
* **🤝 Pragmatist / Samaritan**: The realists. Balances trust with forgiveness to survive noise.

## 🛠️ Development Setup

This project is containerized using Docker and supports VS Code Dev Containers.

### Prerequisites
- Docker & Docker Compose
- VS Code (recommended) with Dev Containers extension

### Running the Simulator

```bash
# Build and start the container
docker-compose up --build

# View logs
docker logs -f sacrificing_simulator
```

## 📊 Output
- **Terminal**: Real-time True Color grid visualization showing territory changes.
- **JSON**: Detailed statistics saved to ./output/, including:
  - Population counts per generation.
  - Extinction events (who died when).
  - Stability detection status.

## ⚙️ Configuration
Adjust `docker-compose.yml` to change:
- `GRID_SIZE`: Size of the world.
- `NOISE`: Probability of communication failure.
- `STABILITY_WINDOW`: How many rounds of stability to wait before auto-stopping.

## 📝 License
Apache License Version 2.0
