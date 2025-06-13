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
        # Use the brick wall background image
        try:
            self.background = SpriteNode('background.jpg', 
                                       position=(self.size.width/2, self.size.height/2))
            self.background.size = self.size
            self.background.z_position = -10  # Behind everything
            self.add_child(self.background)
        except Exception as e:
            print(f"Could not load background image: {e}")
            self.background_color = '#1a1a1a'  # Fallback
        
        self.score = 0
        self.game_over = False
        self.paused = False
        self.last_time = 0
        self.level = 1
        self.ball_radius = 15
        self.bricks = Node(parent=self)
        self.last_milestone = 0
        self.milestone_boost = 1.0
        self.waiting_for_input = False
        
        # Initialize brick entry timing system
        self.entry_times = {
            'next_time': 0,
            'min_delay': 0.3,
            'max_delay': 2.0,
            'speed_factor': 0.9
        }
        
        # Setup background music
        self.setup_background_music()
        
        # Player setup
        try:
            self.player = SpriteNode('pzl:BallBlue', position=(self.size.width/2, self.ball_radius + 10))
            self.player.scale = self.ball_radius / (self.player.size.width/2)
            self.add_child(self.player)
        except Exception as e:
            print(f"Using fallback player: {e}")
            self.player = SpriteNode(color='blue', position=(self.size.width/2, self.ball_radius + 10))
            self.player.size = (self.ball_radius * 2, self.ball_radius * 2)
            self.add_child(self.player)
        
        # UI elements
        self.score_label = LabelNode('Score: 0', position=(100, self.size.height - 30), 
                                     font=('Helvetica', 18), parent=self)
        self.level_label = LabelNode('Level: 1', position=(self.size.width - 100, self.size.height - 30), 
                                     font=('Helvetica', 18), parent=self)
        
        # Pause instruction label
        self.pause_instruction = LabelNode('Tap top-right to pause', 
                                         position=(self.size.width - 120, self.size.height - 60),
                                         font=('Helvetica', 12), 
                                         color='#888888', parent=self)
        
        # Generate first set of bricks
        self.generate_brick_set()
        
        # Set initial time AFTER setup is complete
        self.last_time = self.t
        self.entry_times['next_time'] = self.t + 1.0
    
    def toggle_pause(self):
        """Toggle pause state with visual feedback"""
        self.paused = not self.paused
        
        if self.paused:
            # Create pause overlay
            if not hasattr(self, 'pause_overlay'):
                self.pause_overlay = SpriteNode(color='#00000088', 
                                              size=self.size, 
                                              position=(self.size.width/2, self.size.height/2))
                self.pause_overlay.z_position = 100
                self.add_child(self.pause_overlay)
                
                self.pause_label = LabelNode("PAUSED", 
                                           position=(self.size.width/2, self.size.height/2),
                                           font=('Helvetica Bold', 48), 
                                           color='white', parent=self)
                self.pause_label.z_position = 101
                self.pause_label.shadow = ('black', 0, 0, 3)
                
                self.resume_label = LabelNode("Tap top-right again to resume", 
                                            position=(self.size.width/2, self.size.height/2 - 60),
                                            font=('Helvetica', 20), 
                                            color='#cccccc', parent=self)
                self.resume_label.z_position = 101
        else:
            # Remove pause overlay
            if hasattr(self, 'pause_overlay'):
                self.pause_overlay.remove_from_parent()
                self.pause_label.remove_from_parent()
                self.resume_label.remove_from_parent()
                delattr(self, 'pause_overlay')
                delattr(self, 'pause_label')
                delattr(self, 'resume_label')
    
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
        
        if len(scores) < 5:
            return True
            
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
        """Setup background music with reduced volume"""
        self.bg_music = None
        if sound_available:
            try:
                sound.set_volume(0.08)
                sound.set_honors_silent_switch(False)
                self.bg_music = sound.Player('ode_to_joy.m4a')
                self.bg_music.number_of_loops = -1
                self.bg_music.play()
            except Exception as e:
                print(f"Sound initialization error: {e}")
    
    def stop_background_music(self):
        if sound_available and hasattr(self, 'bg_music') and self.bg_music:
            try:
                self.bg_music.stop()
            except Exception:
                pass
    
    def add_random_brick(self):
        """Add a single random brick at the top of the screen"""
        brick_width = 60
        brick_height = 20
        
        x = random.uniform(brick_width/2, self.size.width - brick_width/2)
        
        colors = ['pzl:Red8', 'pzl:Green8', 'pzl:Yellow8', 'pzl:Purple8', 'pzl:Blue8']
        fallback_colors = ['#ff0000', '#00ff00', '#ffff00', '#800080', '#0000ff']
        color_index = (self.level - 1) % len(colors)
        
        try:
            brick = SpriteNode(colors[color_index], position=(x, self.size.height + brick_height))
        except Exception:
            brick = SpriteNode(color=fallback_colors[color_index], position=(x, self.size.height + brick_height))
        
        brick.size = (brick_width, brick_height)
        # Reduced speed progression for better playability
        brick.speed = min(6, (2 + (self.level * 0.15)) * 1.2 * self.milestone_boost)
        self.bricks.add_child(brick)
        
        base_delay = self.entry_times['max_delay'] * (self.entry_times['speed_factor'] ** (self.level - 1))
        base_delay = max(self.entry_times['min_delay'], base_delay)
        random_delay = random.uniform(base_delay * 0.5, base_delay * 1.5)
        self.entry_times['next_time'] = self.t + random_delay
    
    def clear_bricks(self):
        for brick in list(self.bricks.children):
            brick.remove_from_parent()
    
    def generate_brick_set(self):
        self.clear_bricks()
        
        brick_width = 60
        brick_height = 20
        min_spacing = brick_width / 4
        
        # Progressive brick counts
        if self.level <= 3:
            num_bricks = random.randint(3, 5)
        else:
            num_bricks = min(random.randint(self.level, self.level + 2), 8)
        
        # Create staggered positions
        positions = []
        x = brick_width / 2
        stagger = False  # For alternating rows
        
        while x <= self.size.width - brick_width / 2:
            positions.append(x)
            # Stagger every other position for density
            x += brick_width/2 if stagger else brick_width
            stagger = not stagger
        
        colors = ['pzl:Red8', 'pzl:Green8', 'pzl:Yellow8', 'pzl:Purple8', 'pzl:Blue8']
        fallback_colors = ['#ff0000', '#00ff00', '#ffff00', '#800080', '#0000ff']
        color_index = (self.level - 1) % len(colors)
        
        # Randomly select positions with spacing check
        selected_positions = []
        if positions:
            random.shuffle(positions)
            for pos in positions:
                if all(abs(pos - p) >= brick_width * 1.2 for p in selected_positions):
                    selected_positions.append(pos)
                    if len(selected_positions) == num_bricks:
                        break
        
        # Create bricks with vertical staggering
        vertical_offset = 0
        for i, x in enumerate(selected_positions):
            try:
                brick = SpriteNode(colors[color_index], 
                                position=(x, self.size.height + brick_height + vertical_offset))
            except Exception:
                brick = SpriteNode(color=fallback_colors[color_index],
                                position=(x, self.size.height + brick_height + vertical_offset))
            
            brick.size = (brick_width, brick_height)
            brick.speed = (2 + self.level * 0.15) * 1.15 * self.milestone_boost
            
            # Alternate vertical offset every other brick
            vertical_offset = 40 if i % 2 == 0 else 0
            self.bricks.add_child(brick)
        
        # Enhanced safety checks
        if self.bricks.children:
            self.ensure_safe_passage()
            self.validate_safe_passage()
    
    def check_milestone(self):
        """Check milestone with visual feedback"""
        current_milestone = int(self.score // 20)
        if current_milestone > self.last_milestone:
            self.last_milestone = current_milestone
            self.milestone_boost *= 1.15  # Reduced from 1.33 to 1.15
            self.level += 1
            self.level_label.text = f'Level: {self.level}'
            
            # Level-up flash effect
            self.run_action(Action.sequence(
                Action.scale_to(1.1, 0.1),
                Action.scale_to(1.0, 0.1)
            ))
            
            if sound_available:
                try:
                    sound.play_effect('digital:PowerUp9', volume=0.4)
                except Exception:
                    pass
    
    def ensure_safe_passage(self):
        """Guarantee at least 2 safe passages with larger gaps"""
        # Much larger required gap - ball diameter + substantial safety margin
        required_gap = self.ball_radius * 2 + 30  # Increased from 5 to 30
        
        bricks = sorted(self.bricks.children, key=lambda b: b.position.x)
        if not bricks:
            return
        
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
        
        # Force creation of at least 2 safe gaps
        target_gaps = 2
        attempts = 0
        max_attempts = 10
        
        while len(gaps) < target_gaps and attempts < max_attempts:
            attempts += 1
            
            if len(bricks) <= 1:
                # If only 1 or no bricks, we have plenty of space
                break
            
            # Remove a brick to create more space
            if bricks:
                # Remove from the most crowded area
                brick_to_remove = None
                min_gap = float('inf')
                
                for i, brick in enumerate(bricks):
                    left_gap = 0
                    right_gap = 0
                    
                    if i > 0:
                        left_gap = brick.position.x - bricks[i-1].position.x
                    if i < len(bricks) - 1:
                        right_gap = bricks[i+1].position.x - brick.position.x
                    
                    total_gap = left_gap + right_gap
                    if total_gap < min_gap:
                        min_gap = total_gap
                        brick_to_remove = brick
                
                if brick_to_remove:
                    brick_to_remove.remove_from_parent()
                    bricks.remove(brick_to_remove)
            
            # Recalculate gaps
            gaps = []
            prev_right = 0
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
    
    def validate_safe_passage(self):
        """Final validation to ensure paths exist"""
        required_gap = self.ball_radius * 2 + 20
        bricks = sorted(self.bricks.children, key=lambda b: b.position.x)
        
        safe_paths = 0
        
        # Check left edge
        if not bricks or bricks[0].position.x - bricks[0].size.width/2 >= required_gap:
            safe_paths += 1
        
        # Check gaps between bricks
        for i in range(len(bricks) - 1):
            gap = (bricks[i+1].position.x - bricks[i+1].size.width/2) - \
                  (bricks[i].position.x + bricks[i].size.width/2)
            if gap >= required_gap:
                safe_paths += 1
        
        # Check right edge
        if not bricks or (self.size.width - (bricks[-1].position.x + bricks[-1].size.width/2)) >= required_gap:
            safe_paths += 1
        
        # If less than 2 safe paths, remove more bricks
        while safe_paths < 2 and len(bricks) > 0:
            # Remove the middle brick
            middle_index = len(bricks) // 2
            bricks[middle_index].remove_from_parent()
            bricks.pop(middle_index)
            
            # Recalculate safe paths
            safe_paths = 0
            if not bricks or bricks[0].position.x - bricks[0].size.width/2 >= required_gap:
                safe_paths += 1
            
            for i in range(len(bricks) - 1):
                gap = (bricks[i+1].position.x - bricks[i+1].size.width/2) - \
                      (bricks[i].position.x + bricks[i].size.width/2)
                if gap >= required_gap:
                    safe_paths += 1
            
            if not bricks or (self.size.width - (bricks[-1].position.x + bricks[-1].size.width/2)) >= required_gap:
                safe_paths += 1
    
    def randomize_gap_positions(self):
        """REMOVED - to prevent breaking safe passages"""
        # This function is now empty to prevent shifting that could block paths
        pass
    
    def update(self):
        if self.game_over:
            if hasattr(self, 'game_over_time') and hasattr(self, 'countdown_label'):
                elapsed = self.t - self.game_over_time
                remaining = max(0, 5 - int(elapsed))
                
                if hasattr(self, 'countdown_value') and remaining != self.countdown_value:
                    self.countdown_value = remaining
                    self.countdown_label.text = f'Continuing in {remaining} seconds...'
                
                if remaining == 0 and not hasattr(self, 'high_scores_shown'):
                    self.high_scores_shown = True
                    self.handle_high_score()
            return
        
        # Skip update if paused
        if self.paused:
            return
            
        current_time = self.t
        elapsed = current_time - self.last_time
        self.score += elapsed
        self.score_label.text = f'Score: {int(self.score)}'
        self.last_time = current_time
        
        self.check_milestone()
        
        all_bricks_passed = True
        
        for brick in list(self.bricks.children):
            brick.position = (brick.position.x, brick.position.y - brick.speed)
            
            if brick.position.y < -brick.size.height:
                brick.remove_from_parent()
            else:
                all_bricks_passed = False
                
                if self.check_collision(brick, self.player):
                    self.game_over = True
                    # Screen shake effect on collision
                    self.run_action(Action.sequence(
                        Action.move_by(10, 0, 0.05),
                        Action.move_by(-20, 0, 0.05),
                        Action.move_by(10, 0, 0.05)
                    ))
                    self.stop_background_music()
                    self.show_game_over()
                    break
        
        if self.t >= self.entry_times['next_time']:
            self.add_random_brick()
        
        if all_bricks_passed and len(self.bricks.children) == 0:
            self.level += 1
            self.level_label.text = f'Level: {self.level}'
            self.generate_brick_set()
            
            if sound_available:
                try:
                    sound.play_effect('digital:PowerUp7', volume=0.3)
                except Exception:
                    pass
    
    def check_collision(self, brick, player):
        try:
            circle_x, circle_y = player.position
            
            closest_x = max(brick.position.x - brick.size.width/2, 
                            min(circle_x, brick.position.x + brick.size.width/2))
            closest_y = max(brick.position.y - brick.size.height/2, 
                            min(circle_y, brick.position.y + brick.size.height/2))
            
            distance_x = circle_x - closest_x
            distance_y = circle_y - closest_y
            distance_squared = distance_x**2 + distance_y**2
            
            return distance_squared < (self.ball_radius**2)
        except Exception:
            return False
    
    def reset_game(self):
        self.score = 0
        self.game_over = False
        self.paused = False
        self.last_time = self.t
        self.level = 1
        self.last_milestone = 0
        self.milestone_boost = 1.0
        self.waiting_for_input = False
        
        # Clean up pause elements if they exist
        if hasattr(self, 'pause_overlay'):
            self.pause_overlay.remove_from_parent()
            self.pause_label.remove_from_parent()
            self.resume_label.remove_from_parent()
            delattr(self, 'pause_overlay')
            delattr(self, 'pause_label')
            delattr(self, 'resume_label')
        
        # Remove other attributes
        for attr in ['game_over_time', 'high_scores_shown', 'countdown_label', 'countdown_value']:
            if hasattr(self, attr):
                delattr(self, attr)
        
        self.entry_times['next_time'] = self.t + 1.0
        
        self.score_label.text = 'Score: 0'
        self.level_label.text = 'Level: 1'
        
        self.player.position = (self.size.width/2, self.ball_radius + 10)
        
        for child in list(self.children):
            if child not in [self.player, self.bricks, self.score_label, self.level_label, self.pause_instruction, self.background]:
                child.remove_from_parent()
        
        self.generate_brick_set()
        
        if hasattr(self, 'bg_music') and self.bg_music:
            self.bg_music.play()
    
    def touch_began(self, touch):
        # Check for pause toggle (top-right corner)
        if (touch.location.x > self.size.width - 100 and 
            touch.location.y > self.size.height - 100 and 
            not self.game_over):
            self.toggle_pause()
            return
        
        if self.game_over and not self.waiting_for_input:
            if not hasattr(self, 'high_scores_shown'):
                self.high_scores_shown = True
                self.handle_high_score()
            else:
                self.reset_game()
    
    def touch_moved(self, touch):
        if self.game_over or self.paused:
            return
            
        new_x = touch.location.x
        new_x = max(self.ball_radius, min(new_x, self.size.width - self.ball_radius))
        self.player.position = (new_x, self.player.position.y)
    
    def show_game_over(self):
        try:
            # Clear any existing game over elements first
            for child in list(self.children):
                if hasattr(child, 'is_game_over_element') and child.is_game_over_element:
                    child.remove_from_parent()
            
            # Much darker background - almost black with slight blue tint
            overlay = SpriteNode(color='#000011f8', 
                               size=self.size, 
                               position=(self.size.width/2, self.size.height/2))
            overlay.z_position = 50
            overlay.is_game_over_element = True
            self.add_child(overlay)
            
            # Main game over title - positioned at top
            self.game_over_title = LabelNode('GAME OVER', 
                                      position=(self.size.width/2, self.size.height/2 + 180),
                                      font=('Helvetica Bold', 40), 
                                      color='white')
            self.game_over_title.shadow = ('black', 0, 0, 4)
            self.game_over_title.z_position = 60
            self.game_over_title.is_game_over_element = True
            self.add_child(self.game_over_title)
            
            # Score section - well separated
            self.score_display = LabelNode(f'YOUR SCORE: {int(self.score)}',
                    position=(self.size.width/2, self.size.height/2 + 120),
                    font=('Helvetica Bold', 28), 
                    color='#00ff99')
            self.score_display.shadow = ('black', 0, 0, 3)
            self.score_display.z_position = 60
            self.score_display.is_game_over_element = True
            self.add_child(self.score_display)
            
            # Level display - below score
            self.level_display = LabelNode(f'Level Reached: {self.level}',
                    position=(self.size.width/2, self.size.height/2 + 80),
                    font=('Helvetica', 22), 
                    color='white')
            self.level_display.shadow = ('black', 0, 0, 2)
            self.level_display.z_position = 60
            self.level_display.is_game_over_element = True
            self.add_child(self.level_display)
            
            # Countdown - clearly separated at bottom of score section
            self.countdown_label = LabelNode('Continuing in 5 seconds...',
                    position=(self.size.width/2, self.size.height/2 + 40),
                    font=('Helvetica', 16), 
                    color='#cccccc')
            self.countdown_label.shadow = ('black', 0, 0, 2)
            self.countdown_label.z_position = 60
            self.countdown_label.is_game_over_element = True
            self.add_child(self.countdown_label)
            
            self.game_over_time = self.t
            self.countdown_value = 5
            
            if sound_available:
                try:
                    sound.play_effect('game:Error', volume=0.6)
                except Exception:
                    pass
            
        except Exception as e:
            print(f"Error showing game over: {e}")
    
    def handle_high_score(self):
        final_score = int(self.score)
        is_high_score = self.check_high_score(final_score)
        
        if is_high_score and console_available:
            def name_input_thread():
                try:
                    self.waiting_for_input = True
                    name = console.input_alert(
                        "🏆 NEW HIGH SCORE!",
                        f"Score: {final_score}\nEnter your name:",
                        "",
                        "Save"
                    )
                    self.finalize_high_score(final_score, name)
                except Exception as e:
                    print(f"Error getting player name: {e}")
                    self.display_high_scores(self.load_high_scores())
                finally:
                    self.waiting_for_input = False
            
            t = threading.Thread(target=name_input_thread)
            t.daemon = True
            t.start()
        else:
            self.display_high_scores(self.load_high_scores())
    
    def finalize_high_score(self, score, name):
        high_scores = self.update_high_scores(score, name)
        self.display_high_scores(high_scores)
    
    def display_high_scores(self, high_scores):
        # Clear ALL initial game over elements before showing high scores
        elements_to_clear = ['game_over_title', 'score_display', 'level_display', 'countdown_label']
        for element_name in elements_to_clear:
            if hasattr(self, element_name):
                element = getattr(self, element_name)
                element.remove_from_parent()
                delattr(self, element_name)
        
        # Show fresh "GAME OVER" title at the top
        game_over_clean = LabelNode('GAME OVER', 
                                  position=(self.size.width/2, self.size.height/2 + 180),
                                  font=('Helvetica Bold', 40), 
                                  color='white')
        game_over_clean.shadow = ('black', 0, 0, 4)
        game_over_clean.z_position = 60
        game_over_clean.is_game_over_element = True
        self.add_child(game_over_clean)
        
        # Show final score cleanly
        final_score_clean = LabelNode(f'YOUR SCORE: {int(self.score)}',
                position=(self.size.width/2, self.size.height/2 + 130),
                font=('Helvetica Bold', 26), 
                color='#00ff99')
        final_score_clean.shadow = ('black', 0, 0, 3)
        final_score_clean.z_position = 60
        final_score_clean.is_game_over_element = True
        self.add_child(final_score_clean)
        
        # Dark panel for high scores - positioned well below the score
        scores_panel = SpriteNode(color='#000022ee',
                                size=(420, 360),
                                position=(self.size.width/2, self.size.height/2 - 40))
        scores_panel.stroke_color = '#ffffff99'
        scores_panel.stroke_width = 3
        scores_panel.z_position = 55
        scores_panel.is_game_over_element = True
        self.add_child(scores_panel)
        
        # Title - positioned at top of panel with no overlap
        title_label = LabelNode('🏆 TOP SCORES',
                position=(self.size.width/2, self.size.height/2 + 60),
                font=('Helvetica Bold', 26), 
                color='#ffee44')
        title_label.shadow = ('black', 0, 0, 3)
        title_label.z_position = 60
        title_label.is_game_over_element = True
        self.add_child(title_label)
        
        # High scores list with proper tabbed formatting
        y_position = self.size.height/2 + 10
        for i, entry in enumerate(high_scores[:5]):
            rank_emoji = '⭐' if i == 0 else f'{i+1}.'
            
            # Score column (left aligned)
            score_text = LabelNode(f"{rank_emoji} {entry['score']}",
                    position=(self.size.width/2 - 120, y_position),
                    font=('Helvetica Bold' if i == 0 else 'Helvetica', 18),
                    color='#88ff88' if i == 0 else '#ffffff')
            score_text.shadow = ('black', 0, 0, 2)
            score_text.z_position = 60
            score_text.is_game_over_element = True
            self.add_child(score_text)
            
            # Name column (center)
            name_text = LabelNode(entry['name'],
                    position=(self.size.width/2 - 20, y_position),
                    font=('Helvetica', 16),
                    color='#dddddd')
            name_text.shadow = ('black', 0, 0, 2)
            name_text.z_position = 60
            name_text.is_game_over_element = True
            self.add_child(name_text)
            
            # Date column (right aligned)
            date_text = LabelNode(f"({entry['date']})",
                    position=(self.size.width/2 + 100, y_position),
                    font=('Helvetica', 12),
                    color='#aaaaaa')
            date_text.shadow = ('black', 0, 0, 2)
            date_text.z_position = 60
            date_text.is_game_over_element = True
            self.add_child(date_text)
            
            y_position -= 40  # More spacing between entries
        
        # Restart instruction - positioned well below scores
        restart_label = LabelNode('TAP TO RESTART',
                position=(self.size.width/2, y_position - 30),
                font=('Helvetica Bold', 24),
                color='#ffaa44')
        restart_label.shadow = ('black', 0, 0, 3)
        restart_label.z_position = 60
        restart_label.is_game_over_element = True
        self.add_child(restart_label)

# Run the game
if __name__ == '__main__':
    run(FallingBricksGame(), PORTRAIT)
