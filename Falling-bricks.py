# coding: utf-8
from scene import *
import random
import json
import datetime
import os
import threading

try:
    import console
    console_available = True
except ImportError:
    console_available = False
    print("Console module not available. High scores will be anonymous.")

try:
    import sound
    sound_available = True
except ImportError:
    sound_available = False
    print("Sound module not available. Game will run without sound.")

class FallingBricksGame(Scene):
    def setup(self):
        self.background_color = '#1a1a1a'
        self.score = 0
        self.game_over = False
        self.last_time = 0
        self.level = 1
        self.ball_radius = 15
        self.bricks = Node(parent=self)
        self.last_milestone = 0  # Track the last 20-point milestone reached
        self.milestone_boost = 1.0  # Speed multiplier that increases at milestones
        self.waiting_for_input = False
        
        # Initialize brick entry timing system
        self.entry_times = {
            'next_time': 0,           # Will be set after setup
            'min_delay': 0.3,         # Minimum delay between bricks
            'max_delay': 2.0,         # Maximum delay between bricks
            'speed_factor': 0.9       # Speed increases by 10% per level
        }
        
        # Setup background music
        self.setup_background_music()
        
        # Player setup
        try:
            self.player = SpriteNode('pzl:BallBlue', position=(self.size.width/2, self.ball_radius + 10))
            self.player.scale = self.ball_radius / (self.player.size.width/2)
            self.add_child(self.player)
        except Exception as e:
            # Fallback if sprite asset is not available
            print(f"Using fallback player: {e}")
            self.player = SpriteNode(color='blue', position=(self.size.width/2, self.ball_radius + 10))
            self.player.size = (self.ball_radius * 2, self.ball_radius * 2)
            self.add_child(self.player)
        
        # UI elements
        self.score_label = LabelNode('Score: 0', position=(100, self.size.height - 30), 
                                     font=('Helvetica', 18), parent=self)
        self.level_label = LabelNode('Level: 1', position=(self.size.width - 100, self.size.height - 30), 
                                     font=('Helvetica', 18), parent=self)
        
        # Generate first set of bricks
        self.generate_brick_set()
        
        # Set initial time AFTER setup is complete
        self.last_time = self.t
        self.entry_times['next_time'] = self.t + 1.0  # Initial delay before first random brick
    
    # High score functions
    def load_high_scores(self):
        try:
            if os.path.exists('high_scores.json'):
                with open('high_scores.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading high scores: {e}")
        return []
    
    def save_high_scores(self, scores):
        try:
            with open('high_scores.json', 'w') as f:
                json.dump(scores[:5], f)
        except Exception as e:
            print(f"Error saving high scores: {e}")
    
    def check_high_score(self, score):
        scores = self.load_high_scores()
        
        # If fewer than 5 scores, automatically qualifies
        if len(scores) < 5:
            return True
            
        # Check if score beats any existing entry
        for entry in scores:
            if score > entry.get('score', 0):
                return True
                
        return False
    
    def update_high_scores(self, score, name):
        scores = self.load_high_scores()
        new_entry = {
            'score': score,
            'name': name if name else "Anonymous",
            'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        scores.append(new_entry)
        scores.sort(key=lambda x: x['score'], reverse=True)
        self.save_high_scores(scores[:5])
        return scores[:5]
    
    def setup_background_music(self):
        """Setup the background music player with ode_to_joy.m4a at 15% volume"""
        self.bg_music = None
        if sound_available:
            try:
                # Use proper Pythonista sound API parameters
                sound.set_volume(0.15)  # Set volume to 15%
                sound.set_honors_silent_switch(False)  # Play even when device is muted
                self.bg_music = sound.Player('ode_to_joy.m4a')  # File in same folder
                self.bg_music.number_of_loops = -1  # Loop indefinitely (-1)
                # Start playing immediately
                self.bg_music.play()
            except Exception as e:
                print(f"Sound initialization error: {e}")
    
    def stop_background_music(self):
        """Stop the background music"""
        if sound_available and hasattr(self, 'bg_music') and self.bg_music:
            try:
                self.bg_music.stop()
            except Exception:
                pass
    
    def add_random_brick(self):
        """Add a single random brick at the top of the screen"""
        # Brick properties
        brick_width = 60
        brick_height = 20
        
        # Choose a random horizontal position
        x = random.uniform(brick_width/2, self.size.width - brick_width/2)
        
        # Choose brick color based on level
        colors = ['pzl:Red8', 'pzl:Green8', 'pzl:Yellow8', 'pzl:Purple8', 'pzl:Blue8']
        fallback_colors = ['#ff0000', '#00ff00', '#ffff00', '#800080', '#0000ff']
        color_index = (self.level - 1) % len(colors)
        
        try:
            brick = SpriteNode(colors[color_index], position=(x, self.size.height + brick_height))
        except Exception:
            brick = SpriteNode(color=fallback_colors[color_index], position=(x, self.size.height + brick_height))
        
        brick.size = (brick_width, brick_height)
        # Apply base speed, level modifier, and milestone boost
        brick.speed = (2 + (self.level * 0.2)) * 1.33 * self.milestone_boost
        self.bricks.add_child(brick)
        
        # Schedule next brick entry with randomized timing
        base_delay = self.entry_times['max_delay'] * (self.entry_times['speed_factor'] ** (self.level - 1))
        base_delay = max(self.entry_times['min_delay'], base_delay)
        random_delay = random.uniform(base_delay * 0.5, base_delay * 1.5)
        self.entry_times['next_time'] = self.t + random_delay
    
    def clear_bricks(self):
        # Safely remove each brick individually instead of using remove_all_children()
        for brick in list(self.bricks.children):
            brick.remove_from_parent()
    
    def generate_brick_set(self):
        # Clear existing bricks
        self.clear_bricks()
        
        # Brick properties
        brick_width = 60
        brick_height = 20
        min_spacing = brick_width / 4  # Quarter brick spacing
        
        # Ensure at least 3 bricks
        num_bricks = max(3, min(random.randint(1, self.level + 2), 5))
        
        # Create potential positions with proper spacing
        positions = []
        x = brick_width / 2
        while x <= self.size.width - brick_width / 2:
            positions.append(x)
            x += brick_width + min_spacing
        
        # Brick colors with fallbacks
        colors = ['pzl:Red8', 'pzl:Green8', 'pzl:Yellow8', 'pzl:Purple8', 'pzl:Blue8']
        fallback_colors = ['#ff0000', '#00ff00', '#ffff00', '#800080', '#0000ff']
        color_index = (self.level - 1) % len(colors)
        
        # Randomly select positions
        if positions:  # Check if positions list is not empty
            random.shuffle(positions)
            selected_positions = positions[:num_bricks]
            
            # Create bricks
            for x in selected_positions:
                try:
                    # Try to create brick with sprite
                    brick = SpriteNode(colors[color_index], position=(x, self.size.height + brick_height))
                    brick.size = (brick_width, brick_height)
                except Exception:
                    # Fallback to colored rectangle
                    brick = SpriteNode(color=fallback_colors[color_index], 
                                      position=(x, self.size.height + brick_height))
                    brick.size = (brick_width, brick_height)
                
                # Apply base speed, level modifier, and milestone boost
                brick.speed = (2 + self.level * 0.2) * 1.33 * self.milestone_boost
                
                self.bricks.add_child(brick)
        
        # Ensure and randomize safe passages
        if self.bricks.children:
            self.ensure_safe_passage()
            self.randomize_gap_positions()
    
    def check_milestone(self):
        """Check if player reached a 20-point milestone and apply boost if needed"""
        current_milestone = int(self.score // 20)  # Changed from 50 to 20
        if current_milestone > self.last_milestone:
            # Player reached a new 20-point milestone
            self.last_milestone = current_milestone
            self.milestone_boost *= 1.33  # Apply additional 33% boost
            self.level += 1  # Increase level at each milestone
            self.level_label.text = f'Level: {self.level}'
            
            # Visual/audio feedback for milestone
            if sound_available:
                try:
                    sound.play_effect('digital:PowerUp9')
                except Exception:
                    pass
    
    def ensure_safe_passage(self):
        # Ball's required clearance (diameter)
        required_gap = self.ball_radius * 2 + 5  # 35 units
        
        # Get current brick positions sorted left-to-right
        bricks = sorted(self.bricks.children, key=lambda b: b.position.x)
        
        # Check existing gaps including screen edges
        gaps = []
        prev_right = 0  # Left screen edge
        
        for brick in bricks:
            current_left = brick.position.x - brick.size.width/2
            gap = current_left - prev_right
            if gap >= required_gap:
                gaps.append((prev_right, current_left))
            prev_right = brick.position.x + brick.size.width/2
        
        # Check right screen edge
        gap = self.size.width - prev_right
        if gap >= required_gap:
            gaps.append((prev_right, self.size.width))
        
        # If enough gaps exist, do nothing
        if len(gaps) >= 2:
            return
        
        # Create necessary gaps by repositioning bricks
        target_gaps = 2
        created_gaps = 0
        
        # First ensure left screen edge gap
        if not any(g[0] == 0 for g in gaps):
            # Make space at far left
            if bricks:
                leftmost = bricks[0]
                new_x = required_gap + leftmost.size.width/2
                if new_x < leftmost.position.x:
                    leftmost.position.x = new_x
                    created_gaps += 1
        
        # Then ensure right screen edge gap
        if not any(g[1] == self.size.width for g in gaps):
            if bricks:
                rightmost = bricks[-1]
                new_x = self.size.width - required_gap - rightmost.size.width/2
                if new_x > rightmost.position.x:
                    rightmost.position.x = new_x
                    created_gaps += 1
        
        # Create middle gaps if still needed
        if created_gaps < target_gaps and len(bricks) >= 2:
            # Find largest existing gap between bricks
            max_gap_size = 0
            max_gap_index = -1
            for i in range(1, len(bricks)):
                gap = (bricks[i].position.x - bricks[i].size.width/2) - \
                      (bricks[i-1].position.x + bricks[i-1].size.width/2)
                if gap > max_gap_size:
                    max_gap_size = gap
                    max_gap_index = i
            
            # Enlarge the largest gap if possible
            if max_gap_size > 0 and max_gap_index != -1:
                left_brick = bricks[max_gap_index-1]
                right_brick = bricks[max_gap_index]
                needed_space = required_gap - max_gap_size
                
                if needed_space > 0:
                    # Calculate available movement space
                    left_available = left_brick.position.x - left_brick.size.width/2
                    right_available = self.size.width - (right_brick.position.x + right_brick.size.width/2)
                    
                    # Distribute space adjustment
                    left_adjust = min(needed_space/2, left_available)
                    right_adjust = min(needed_space/2, right_available)
                    
                    # Reposition bricks
                    left_brick.position.x -= left_adjust
                    right_brick.position.x += right_adjust
                    created_gaps += 1

        # Final check and fallback
        if created_gaps < target_gaps and len(bricks) > 0:
            # Remove middle brick to create emergency gap
            middle_index = len(bricks) // 2
            bricks[middle_index].remove_from_parent()
    
    def randomize_gap_positions(self):
        """Randomizes horizontal positions of safe gaps"""
        if not self.bricks.children:
            return
        
        bricks = sorted(self.bricks.children, key=lambda b: b.position.x)
        if not bricks:
            return
            
        brick_width = bricks[0].size.width
        
        # Calculate formation boundaries
        leftmost = bricks[0].position.x - brick_width/2
        rightmost = bricks[-1].position.x + brick_width/2
        
        # Calculate maximum safe shift range
        max_shift_left = leftmost
        max_shift_right = self.size.width - rightmost
        
        if max_shift_left + max_shift_right > 0:
            # Apply random shift within safe limits
            shift = random.uniform(-max_shift_left, max_shift_right)
            for brick in bricks:
                brick.position.x += shift
    
    def update(self):
        if self.game_over:
            # Check if game over screen has been shown for 5 seconds
            if hasattr(self, 'game_over_time') and hasattr(self, 'countdown_label'):
                elapsed = self.t - self.game_over_time
                remaining = max(0, 5 - int(elapsed))  # Changed from 15 to 5 seconds
                
                # Update the countdown display
                if hasattr(self, 'countdown_value') and remaining != self.countdown_value:
                    self.countdown_value = remaining
                    self.countdown_label.text = f'Continuing in {remaining} seconds...'
                
                # Transition when timer reaches zero
                if remaining == 0 and not hasattr(self, 'high_scores_shown'):
                    self.high_scores_shown = True
                    self.handle_high_score()
            return
            
        # Update score with proper time delta
        current_time = self.t
        elapsed = current_time - self.last_time
        self.score += elapsed
        self.score_label.text = f'Score: {int(self.score)}'
        self.last_time = current_time
        
        # Check for 20-point milestones
        self.check_milestone()
        
        # Check if all bricks have passed
        all_bricks_passed = True
        
        # Update brick positions and check collisions
        for brick in list(self.bricks.children):
            # Move brick down
            brick.position = (brick.position.x, brick.position.y - brick.speed)
            
            # Check if brick reached bottom
            if brick.position.y < -brick.size.height:
                brick.remove_from_parent()
            else:
                all_bricks_passed = False
                
                # Check collision with player
                if self.check_collision(brick, self.player):
                    self.game_over = True
                    self.stop_background_music()  # Stop music before game over
                    self.show_game_over()
                    break
        
        # Check if it's time to add a new random brick
        if self.t >= self.entry_times['next_time']:
            self.add_random_brick()
        
        # If all bricks have passed, generate a new set and increase level
        if all_bricks_passed and len(self.bricks.children) == 0:
            self.level += 1
            self.level_label.text = f'Level: {self.level}'
            self.generate_brick_set()
            
            # Play sound effect if available
            if sound_available:
                try:
                    sound.play_effect('digital:PowerUp7')
                except Exception:
                    pass  # Continue if sound fails
    
    def check_collision(self, brick, player):
        # Circle-rectangle collision detection
        try:
            circle_x, circle_y = player.position
            
            # Find closest point on rectangle to circle
            closest_x = max(brick.position.x - brick.size.width/2, 
                            min(circle_x, brick.position.x + brick.size.width/2))
            closest_y = max(brick.position.y - brick.size.height/2, 
                            min(circle_y, brick.position.y + brick.size.height/2))
            
            # Calculate distance
            distance_x = circle_x - closest_x
            distance_y = circle_y - closest_y
            distance_squared = distance_x**2 + distance_y**2
            
            return distance_squared < (self.ball_radius**2)
        except Exception:
            return False  # Default to no collision on error
    
    def reset_game(self):
        # Reset game state
        self.score = 0
        self.game_over = False
        self.last_time = self.t  # Use current time for reset
        self.level = 1
        self.last_milestone = 0  # Reset milestone tracking
        self.milestone_boost = 1.0  # Reset speed boost
        self.waiting_for_input = False
        
        # Remove timeout attributes
        if hasattr(self, 'game_over_time'):
            delattr(self, 'game_over_time')
        if hasattr(self, 'high_scores_shown'):
            delattr(self, 'high_scores_shown')
        if hasattr(self, 'countdown_label'):
            delattr(self, 'countdown_label')
        if hasattr(self, 'countdown_value'):
            delattr(self, 'countdown_value')
        
        # Reset brick entry timing
        self.entry_times['next_time'] = self.t + 1.0
        
        # Update UI
        self.score_label.text = 'Score: 0'
        self.level_label.text = 'Level: 1'
        
        # Reset player position
        self.player.position = (self.size.width/2, self.ball_radius + 10)
        
        # Remove game over UI elements
        for child in list(self.children):
            if child != self.player and child != self.bricks and child != self.score_label and child != self.level_label:
                child.remove_from_parent()
        
        # Generate new bricks
        self.generate_brick_set()
        
        # Restart background music
        if hasattr(self, 'bg_music') and self.bg_music:
            self.bg_music.play()
    
    def touch_began(self, touch):
        if self.game_over and not self.waiting_for_input:
            if not hasattr(self, 'high_scores_shown'):
                # If high scores aren't shown yet, show them instead of resetting
                self.high_scores_shown = True
                self.handle_high_score()
            else:
                # Otherwise reset the game
                self.reset_game()
    
    def touch_moved(self, touch):
        if self.game_over:
            return
            
        # Move player horizontally based on touch
        new_x = touch.location.x
        # Keep player within screen bounds
        new_x = max(self.ball_radius, min(new_x, self.size.width - self.ball_radius))
        self.player.position = (new_x, self.player.position.y)
    
    def show_game_over(self):
        try:
            # First show the game over screen
            overlay = SpriteNode(color='#00000099', 
                               size=self.size, 
                               position=(self.size.width/2, self.size.height/2))
            self.add_child(overlay)
            
            LabelNode('Game Over!', 
                    position=(self.size.width/2, self.size.height/2 + 50),
                    font=('Helvetica', 30),
                    parent=self)
            
            LabelNode(f'Final Score: {int(self.score)}',
                    position=(self.size.width/2, self.size.height/2),
                    font=('Helvetica', 20),
                    parent=self)
            
            LabelNode(f'Level Reached: {self.level}',
                    position=(self.size.width/2, self.size.height/2 - 30),
                    font=('Helvetica', 20),
                    parent=self)
            
            # Add countdown indicator as a dynamic label with 5 second countdown
            self.countdown_label = LabelNode('Continuing in 5 seconds...',
                    position=(self.size.width/2, self.size.height/2 - 60),
                    font=('Helvetica', 16),
                    parent=self)
            
            # Record when game over screen was shown and set initial countdown value
            self.game_over_time = self.t
            self.countdown_value = 5  # Changed from 15 to 5
            
            # Play game over sound
            if sound_available:
                try:
                    sound.play_effect('game:Error')
                except Exception:
                    pass  # Continue if sound fails
            
        except Exception as e:
            print(f"Error showing game over: {e}")
    
    def handle_high_score(self):
        """Handle high score after game over screen is displayed"""
        final_score = int(self.score)
        is_high_score = self.check_high_score(final_score)
        
        # Get player name if it's a high score
        player_name = "Anonymous"
        
        if is_high_score and console_available:
            # Run name input in a separate thread to avoid blocking
            def name_input_thread():
                try:
                    self.waiting_for_input = True
                    name = console.input_alert(
                        "New High Score!",
                        f"Your score: {final_score}. Enter your name:",
                        "",
                        "Save"
                    )
                    # Process results on the main thread
                    self.finalize_high_score(final_score, name)
                except Exception as e:
                    print(f"Error getting player name: {e}")
                    # Show scores even if there was an error
                    self.display_high_scores(self.load_high_scores())
                finally:
                    self.waiting_for_input = False
            
            # Start the thread
            t = threading.Thread(target=name_input_thread)
            t.daemon = True
            t.start()
        else:
            # No high score or console not available
            self.display_high_scores(self.load_high_scores())
    
    def finalize_high_score(self, score, name):
        """Update high scores and display results after name input"""
        high_scores = self.update_high_scores(score, name)
        self.display_high_scores(high_scores)
    
    def display_high_scores(self, high_scores):
        # Display high scores on game over screen
        y_position = self.size.height/2 - 80
        LabelNode('Top Scores:',
                position=(self.size.width/2, y_position),
                font=('Helvetica', 18),
                parent=self)
        y_position -= 30
        
        for i, entry in enumerate(high_scores[:5]):
            emoji = '⭐️' if i == 0 else f'{i+1}.'
            text = f"{emoji} {entry['score']} - {entry['name']} ({entry['date']})"
            LabelNode(text,
                    position=(self.size.width/2, y_position),
                    font=('Helvetica', 14),
                    parent=self)
            y_position -= 25
        
        LabelNode('Tap to Restart',
                position=(self.size.width/2, y_position),
                font=('Helvetica', 18),
                parent=self)

# Run the game
if __name__ == '__main__':
    run(FallingBricksGame(), PORTRAIT)
