# The Evolution of Sacrificing

> A simulation of the **Alarm Call Game** exploring how altruistic self-sacrifice traits can evolve and survive in a hostile environment.

## 🦁 The Game Mechanics

This is not a standard Prisoner's Dilemma. It models a survival scenario:
1. **Danger Arrives**: A predator approaches two agents.
2. **Spotting**: Agents have a probability (e.g., 50%) to spot the danger independently.
3. **The Decision**:
   - If you spot danger, you can **Notify** (Risk death to warn neighbor) or **Run** (100% survival).
   - If you don't spot danger, your survival depends on your neighbor warning you.
4. **Noise**: Warnings can be lost due to environmental noise (rain, wind), leading to tragedy.

## 🧠 Strategies

The simulation currently includes:
- **😇 Altruist**: Always warns neighbors. High risk, high group benefit.
- **😈 Cheater**: Always runs. Zero risk, parasitic behavior.
- **🧐 Selective**: Warns only "trusted" types (Kin or Altruists). Default distrust.
- **😡 Grudger**: Warns everyone except known bad actors (Cheaters). Default trust.
- **🎭 Imposter**: Looks like an Altruist (inherits from it) but acts like a Cheater.
- **🤪 Chaotic**: Randomly chooses to Notify or Run.
- **🧱 Xenophobe**: Only helps its exact own kind.

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
