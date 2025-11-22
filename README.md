# The Evolution of Sacrificing

> A simulation of the **Alarm Call Game** exploring how altruistic self-sacrifice traits can evolve and survive in a hostile environment.

## 📖 Overview

This project is a spiritual successor to [The Evolution of Cooperation](https://github.com/rrushtw/the_evolution_of_cooperation). While the previous project focused on the Iterated Prisoner's Dilemma (IPD) and score accumulation, this project introduces **mortality** and **spatial dynamics**.

Key differences from the previous project:
- **Mechanism**: Based on the **Alarm Call Game** (warning others at a risk to oneself).
- **Environment**: A spatial **Grid World** where neighbors matter.
- **Evolution**: Agents do not just accumulate points; they **die** (removed from the grid) and **reproduce** (fill empty spots based on fitness).

## 🧪 Strategies

The simulation initially explores three core strategies:
- **Altruist (The Sacrificer)**: Always warns neighbors of danger, risking their own life to save others.
- **Cheater (The Free-rider)**: Never warns others, prioritizing their own survival.
- **Discriminator**: Conditionally warns others based on their perceived strategy (e.g., only helping other altruists).

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

### Project Structure
- `src/`: Core simulation logic.
- `strategies/`: Python scripts defining agent behaviors.
- `output/`: Simulation results and JSON logs.

## 📝 License
Apache License Version 2.0
