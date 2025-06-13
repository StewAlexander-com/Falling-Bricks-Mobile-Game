# Falling Bricks Game

### Click the below image to see an intro video …
[![YouTube Short Thumbnail](https://img.youtube.com/vi/LvjWiNNIV68/maxresdefault.jpg)](https://youtube.com/shorts/LvjWiNNIV68)

---

_**Falling Bricks**_ is a dynamic arcade-style game for iOS where you control a ball to dodge falling bricks. Survive as long as possible while climbing levels and competing for high scores!

## Features

### Core Gameplay
- 🕹️ **Intuitive Touch Controls**: Simple one-touch horizontal drag control
- 🎯 **Smart Collision Detection**: Precise circle-to-rectangle collision system
- 🛡️ **Safe Passage Algorithm**: Ensures at least 2 playable paths through brick formations
- ⚡ **Progressive Difficulty**: Speed and complexity increase every 20 points
- 🏆 **Persistent High Score System**: Top 5 scores saved with player names and timestamps

### Visual & Audio Experience
- 🎨 **Dynamic Visual Levels**: Brick colors change with each level progression
- 🌌 **Background Graphics**: Custom background image support
- 💥 **Screen Shake Effects**: Visual feedback on collisions
- 🎶 **Background Music**: 8-bit rendition of Beethoven's "Ode to Joy"
- 🔊 **Sound Effects**: Audio feedback for game events and level progression

### Advanced Features
- ⏸️ **Pause Functionality**: Tap top-right corner to pause/resume game
- ⏱️ **5-Second Auto-Advance**: Automatic transition from game over to high scores
- 🎮 **Milestone Boost System**: Enhanced difficulty scaling with achievement rewards
- 🧠 **Intelligent Brick Spawning**: Dynamic timing system prevents impossible scenarios
- 📱 **Portrait Orientation**: Optimized for mobile gameplay

## Installation

### Requirements:
- iOS device with [Pythonista 3](https://omz-software.com/pythonista/) installed

### Setup:
1. **Clone Repository**  
   ```bash
   git clone https://github.com/StewAlexander-com/Falling-Bricks-Mobile-Game.git
   ```

2. **Import Files to Pythonista**  
   Transfer the following files to Pythonista's documents folder (Files → iCloud → Pythonista):
   - `Falling-bricks.py` (main game file)
   - `ode_to_joy.m4a` (background music)
   - `background.jpg` (background image)

3. **Run Game**  
   - Open Pythonista 3
   - Navigate to `Falling-bricks.py`
   - Tap the play button ▶️

## How to Play

- **Touch & Drag**: Move ball horizontally across the screen
- **Avoid**: Falling bricks of various colors
- **Survive**: Stay alive as long as possible to increase your score
- **Level Up**: Earn 20 points to advance levels (increased speed + new brick colors)
- **Pause**: Tap the top-right corner to pause/resume gameplay
- **High Scores**: Enter your name when achieving a top-5 score

## Game Mechanics

### Scoring System
- **Continuous Scoring**: Points accumulate based on survival time
- **Level Progression**: Every 20 points advances to the next level
- **Milestone Boosts**: Speed multiplier increases with each level (15% boost per level)

### Difficulty Scaling
- **Brick Speed**: Increases progressively with each level
- **Spawn Timing**: Dynamic brick entry timing becomes more challenging
- **Visual Complexity**: More bricks spawn as levels advance
- **Safe Passage**: Algorithm ensures playable paths remain available

## High Score System

- **Top 5 Leaderboard**: Best scores persist between game sessions
- **Player Names**: High score achievers can enter their name
- **Timestamps**: Date and time recorded for each high score
- **JSON Storage**: Scores saved locally in `high_scores.json`

## Technical Features

### Framework & Dependencies
- **Pythonista Scene**: Built on Pythonista's Scene framework
- **Sound Integration**: Uses Pythonista's sound module for audio
- **Console Integration**: Player name input via console alerts
- **JSON Persistence**: High score data storage and retrieval

### Performance Optimizations
- **Collision Optimization**: Efficient circle-to-rectangle collision detection
- **Memory Management**: Automatic cleanup of off-screen game objects
- **Thread Safety**: Background threading for user input handling
- **Error Handling**: Graceful fallbacks for missing resources

## Roadmap

### Planned Enhancements:
- 🌆 **Multiple Background Themes**: Selectable visual environments
- ✨ **Power-up Items**: Collectible bonuses and special abilities
- 🧩 **Special Brick Patterns**: Unique formations and brick types
- 🎚️ **Difficulty Settings**: User-selectable challenge levels
- 📊 **Extended Stats**: Detailed gameplay analytics and achievements

### Future Considerations:
- ☁️ **Cloud-synced High Scores**: Cross-device score synchronization
- 📳 **Haptic Feedback**: Tactile response integration
- 🎨 **Ball Customization**: Selectable player character designs
- 📏 **Dynamic Brick Sizes**: Variable brick dimensions for added complexity
- 🎵 **Multiple Music Tracks**: Expanded audio library

## File Structure

```
Falling-Bricks-Mobile-Game/
├── Falling-bricks.py          # Main game engine
├── ode_to_joy.m4a            # Background music file
├── background.jpg            # Background image
├── high_scores.json          # Generated high score data
└── README.md                 # This documentation
```

## Credits

- **Game Engine**: Developed using Pythonista's Scene framework
- **Background Music**: Public domain arrangement of Beethoven's "Ode to Joy"
- **Sound Effects**: Pythonista's built-in sound library
- **Development**: Python implementation with iOS optimization

---

**Enjoy the game!** 🕹️ 

Report bugs or suggest features by opening an issue on this repository.