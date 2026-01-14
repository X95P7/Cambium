package net.famzangl.minecraft.minebot.ai;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.famzangl.minecraft.minebot.ai.cambiumInputs.APIClient;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.minecraft.client.Minecraft;
import net.minecraft.entity.Entity;
import net.minecraft.entity.EntityLivingBase;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraft.util.DamageSource;
import net.minecraftforge.event.entity.living.LivingHurtEvent;
import net.minecraftforge.event.entity.player.AttackEntityEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;

/**
 * RewardListener - Detects combat events and sends rewards to the API
 * Tracks damage dealt, damage taken, and other combat-related events
 */
public class RewardListener {
    
    // Track previous health to detect damage taken
    private float lastHealth = -1.0f;
    private long lastDamageTakenTime = 0;
    private static final long DAMAGE_COOLDOWN_MS = 100; // 100ms cooldown between damage events
    
    // Track last attack to detect damage dealt
    private Entity lastAttackedEntity = null;
    private float lastAttackedEntityHealth = -1.0f;
    private long lastDamageDealtTime = 0;
    
    // Track aim checking
    private long lastAimCheckTime = 0;
    private static final long AIM_CHECK_INTERVAL_MS = 100; // Check aim every 100ms
    
    // Track damage detection via tick
    private long lastDamageCheckTime = 0;
    private static final long DAMAGE_CHECK_INTERVAL_MS = 50; // Check damage every 50ms
    private boolean isAttacking = false; // Track if player is currently attacking
    private long lastAttackStartTime = 0;
    
    @SubscribeEvent
    public void onLivingHurt(LivingHurtEvent event) {
        // Debug: Log that event fired
        System.out.println("[RewardListener] LivingHurtEvent fired - isRemote: " + event.entity.worldObj.isRemote);
        
        // Only process on client side
        if (!event.entity.worldObj.isRemote) {
            return;
        }
        
        EntityLivingBase entity = event.entityLiving;
        DamageSource source = event.source;
        float damage = event.ammount; // Note: Forge 1.8.9 uses "ammount" (typo in API)
        
        Minecraft mc = Minecraft.getMinecraft();
        if (mc.thePlayer == null) {
            return;
        }
        
        // Check if our bot took damage
        if (entity instanceof EntityPlayer && entity.equals(mc.thePlayer)) {
            EntityPlayer player = (EntityPlayer) entity;
            String botName = player.getName();
            
            // Prevent duplicate damage events within cooldown
            long currentTime = System.currentTimeMillis();
            if (currentTime - lastDamageTakenTime < DAMAGE_COOLDOWN_MS) {
                return;
            }
            lastDamageTakenTime = currentTime;
            
            // Send damage_taken event
            JsonArray events = new JsonArray();
            JsonObject damageEvent = new JsonObject();
            damageEvent.addProperty("type", "damage_taken");
            damageEvent.addProperty("amount", damage);
            if (source.getEntity() != null) {
                damageEvent.addProperty("attacker", source.getEntity().getName());
            }
            events.add(damageEvent);
            
            System.out.println("[RewardListener] [EVENT] Bot " + botName + " took " + damage + " damage");
            sendRewardEvents(events);
            
            // Update last health
            lastHealth = player.getHealth() - damage; // Health after taking damage
        }
        
        // Check if our bot dealt damage to another entity
        if (source.getEntity() instanceof EntityPlayer && source.getEntity().equals(mc.thePlayer)) {
            EntityPlayer attacker = (EntityPlayer) source.getEntity();
            String botName = attacker.getName();
            
            // Prevent duplicate damage events within cooldown
            long currentTime = System.currentTimeMillis();
            if (currentTime - lastDamageDealtTime < DAMAGE_COOLDOWN_MS) {
                return;
            }
            
            // Only send if we're attacking a player (PvP)
            if (entity instanceof EntityPlayer) {
                lastDamageDealtTime = currentTime;
                
                EntityPlayer target = (EntityPlayer) entity;
                float targetMaxHealth = target.getMaxHealth();
                
                // Calculate damage as percentage of target's max health
                // This makes rewards scale with how much damage relative to target health
                float damagePercentage = (damage / targetMaxHealth);
                // Cap at 1.0 (100% of max health)
                if (damagePercentage > 1.0f) damagePercentage = 1.0f;
                
                // Send damage_dealt event with percentage-based reward
                JsonArray events = new JsonArray();
                JsonObject damageEvent = new JsonObject();
                damageEvent.addProperty("type", "damage_dealt");
                damageEvent.addProperty("amount", damage); // Raw damage for tracking
                damageEvent.addProperty("damage_percentage", damagePercentage); // Percentage for reward scaling
                damageEvent.addProperty("target", entity.getName());
                events.add(damageEvent);
                
                System.out.println("[RewardListener] [EVENT] Bot " + botName + " dealt " + damage + " damage (" + (damagePercentage * 100) + "%) to " + entity.getName());
                sendRewardEvents(events);
                
                // Track target health for future reference
                lastAttackedEntity = entity;
                lastAttackedEntityHealth = target.getHealth();
            }
        }
    }
    
    @SubscribeEvent
    public void onAttackEntity(AttackEntityEvent event) {
        // Debug: Log that event fired
        System.out.println("[RewardListener] AttackEntityEvent fired - isRemote: " + event.entity.worldObj.isRemote);
        
        // This fires when player clicks to attack, before damage is calculated
        // We can use this to track attack attempts
        if (event.entity.worldObj.isRemote && event.entity instanceof EntityPlayer) {
            EntityPlayer player = (EntityPlayer) event.entity;
            Minecraft mc = Minecraft.getMinecraft();
            
            if (player.equals(mc.thePlayer) && event.target instanceof EntityPlayer) {
                // Bot is attacking another player - track this for damage detection
                lastAttackedEntity = event.target;
                lastAttackedEntityHealth = ((EntityPlayer) event.target).getHealth();
                isAttacking = true;
                lastAttackStartTime = System.currentTimeMillis();
                System.out.println("[RewardListener] [EVENT] Bot started attacking " + event.target.getName());
            }
        }
    }
    
    /**
     * Periodically checks if bot is aiming at enemies and sends good_aim rewards
     * Also detects damage taken/dealt via health monitoring (tick-based detection)
     * Uses percentage-based scoring: perfect aim = 1.0, within 90 degrees = 0.05
     */
    @SubscribeEvent
    public void onClientTick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) {
            return;
        }
        
        Minecraft mc = Minecraft.getMinecraft();
        if (mc.thePlayer == null || mc.theWorld == null) {
            return;
        }
        
        EntityPlayer player = mc.thePlayer;
        long currentTime = System.currentTimeMillis();
        
        // Check for damage taken/dealt every DAMAGE_CHECK_INTERVAL_MS
        if (currentTime - lastDamageCheckTime >= DAMAGE_CHECK_INTERVAL_MS) {
            lastDamageCheckTime = currentTime;
            checkDamageTaken(player, currentTime);
            checkDamageDealt(player, mc, currentTime);
        }
        
        // Check aim every AIM_CHECK_INTERVAL_MS
        if (currentTime - lastAimCheckTime < AIM_CHECK_INTERVAL_MS) {
            return;
        }
        lastAimCheckTime = currentTime;
        
        // Find closest enemy player
        EntityPlayer closestEnemy = null;
        double closestDistance = Double.MAX_VALUE;
        
        for (Object obj : mc.theWorld.loadedEntityList) {
            if (obj instanceof EntityPlayer && !obj.equals(player)) {
                EntityPlayer enemy = (EntityPlayer) obj;
                if (enemy.isDead || enemy.getHealth() <= 0) {
                    continue;
                }
                
                double dx = enemy.posX - player.posX;
                double dy = enemy.posY - player.posY;
                double dz = enemy.posZ - player.posZ;
                double distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
                
                if (distance < closestDistance && distance < 50.0) { // Only check within 50 blocks
                    closestDistance = distance;
                    closestEnemy = enemy;
                }
            }
        }
        
        if (closestEnemy != null) {
            // Calculate angle to enemy
            double dx = closestEnemy.posX - player.posX;
            double dy = closestEnemy.posY - player.posY;
            double dz = closestEnemy.posZ - player.posZ;
            
            // Calculate target yaw (angle in horizontal plane)
            double targetYaw = Math.atan2(dx, dz) * 180.0 / Math.PI;
            
            // Calculate target pitch (angle in vertical plane)
            double horizontalDist = Math.sqrt(dx * dx + dz * dz);
            double targetPitch = -Math.atan2(dy, horizontalDist) * 180.0 / Math.PI;
            
            // Get player's current rotation
            float playerYaw = player.rotationYaw;
            float playerPitch = player.rotationPitch;
            
            // Normalize angles to -180 to 180 range
            playerYaw = normalizeYaw(playerYaw);
            targetYaw = normalizeYaw(targetYaw);
            
            // Calculate angle differences
            double yawDiff = Math.abs(normalizeYaw(playerYaw - targetYaw));
            double pitchDiff = Math.abs(playerPitch - targetPitch);
            
            // Get maximum angle difference (worst case)
            double maxAngle = Math.max(yawDiff, pitchDiff);
            
            // If player is looking at enemy (within 30 degrees) and close (within 5 blocks), 
            // track this enemy for damage detection (in case AttackEntityEvent doesn't fire)
            if (maxAngle < 30.0 && closestDistance < 5.0) {
                // Check if attack key might be pressed (check if player is swinging)
                boolean mightBeAttacking = player.isSwingInProgress || 
                                          (player.swingProgress > 0 && player.swingProgress < 1.0f);
                
                if (mightBeAttacking || isAttacking) {
                    // Track this enemy for damage detection
                    if (lastAttackedEntity == null || !lastAttackedEntity.equals(closestEnemy)) {
                        lastAttackedEntity = closestEnemy;
                        lastAttackedEntityHealth = closestEnemy.getHealth();
                        isAttacking = true;
                        lastAttackStartTime = currentTime;
                    }
                }
            }
            
            // Calculate aim score (percentage-based, same as backend)
            // Perfect aim (within 5 degrees) = 1.0
            // Within 10 degrees = 0.8
            // Within 20 degrees = 0.5
            // Within 45 degrees = 0.2
            // Within 90 degrees = 0.05
            double aimScore = 0.0;
            if (maxAngle < 5) {
                aimScore = 1.0;
            } else if (maxAngle < 10) {
                aimScore = 0.8;
            } else if (maxAngle < 20) {
                aimScore = 0.5;
            } else if (maxAngle < 45) {
                aimScore = 0.2;
            } else if (maxAngle < 90) {
                aimScore = 0.05;
            }
            
            // Only send good_aim event if score > 0 (bot is looking roughly at enemy)
            if (aimScore > 0) {
                JsonArray events = new JsonArray();
                JsonObject aimEvent = new JsonObject();
                aimEvent.addProperty("type", "good_aim");
                aimEvent.addProperty("amount", aimScore); // Percentage-based score (0.0 to 1.0)
                aimEvent.addProperty("yaw_diff", yawDiff);
                aimEvent.addProperty("pitch_diff", pitchDiff);
                aimEvent.addProperty("distance", closestDistance);
                events.add(aimEvent);
                
                // Debug log (commented out to reduce spam - uncomment if needed)
                // System.out.println("[RewardListener] Good aim detected: score=" + aimScore + ", yaw_diff=" + yawDiff + ", pitch_diff=" + pitchDiff);
                sendRewardEvents(events);
            }
        }
    }
    
    /**
     * Checks if bot took damage by monitoring health changes
     */
    private void checkDamageTaken(EntityPlayer player, long currentTime) {
        float currentHealth = player.getHealth();
        
        // Initialize lastHealth on first run
        if (lastHealth < 0) {
            lastHealth = currentHealth;
            return;
        }
        
        // Check if health decreased (damage taken)
        if (currentHealth < lastHealth) {
            float damage = lastHealth - currentHealth;
            
            // Ignore very small changes (could be regeneration or rounding)
            if (damage < 0.1f) {
                lastHealth = currentHealth;
                return;
            }
            
            // Prevent duplicate damage events within cooldown
            if (currentTime - lastDamageTakenTime < DAMAGE_COOLDOWN_MS) {
                lastHealth = currentHealth;
                return;
            }
            lastDamageTakenTime = currentTime;
            
            // Send damage_taken event
            JsonArray events = new JsonArray();
            JsonObject damageEvent = new JsonObject();
            damageEvent.addProperty("type", "damage_taken");
            damageEvent.addProperty("amount", damage);
            
            // Try to find attacker by checking nearby entities
            String attackerName = findAttacker(player);
            if (attackerName != null) {
                damageEvent.addProperty("attacker", attackerName);
            }
            
            events.add(damageEvent);
            
            String botName = player.getName();
            System.out.println("[RewardListener] [TICK] Bot " + botName + " took " + damage + " damage (health: " + lastHealth + " -> " + currentHealth + ")");
            sendRewardEvents(events);
        }
        
        lastHealth = currentHealth;
    }
    
    /**
     * Checks if bot dealt damage by monitoring enemy health changes
     */
    private void checkDamageDealt(EntityPlayer player, Minecraft mc, long currentTime) {
        // Only check if we're currently attacking or recently attacked
        if (lastAttackedEntity == null || !(lastAttackedEntity instanceof EntityPlayer)) {
            // Reset attack state if too much time has passed
            if (isAttacking && currentTime - lastAttackStartTime > 2000) {
                isAttacking = false;
            }
            return;
        }
        
        EntityPlayer target = (EntityPlayer) lastAttackedEntity;
        
        // Check if target is still valid
        if (target.isDead || target.getHealth() <= 0) {
            lastAttackedEntity = null;
            lastAttackedEntityHealth = -1.0f;
            isAttacking = false;
            return;
        }
        
        float currentTargetHealth = target.getHealth();
        
        // Initialize target health on first check
        if (lastAttackedEntityHealth < 0) {
            lastAttackedEntityHealth = currentTargetHealth;
            return;
        }
        
        // Check if target health decreased (damage dealt)
        if (currentTargetHealth < lastAttackedEntityHealth) {
            float damage = lastAttackedEntityHealth - currentTargetHealth;
            
            // Ignore very small changes (could be regeneration or rounding)
            if (damage < 0.1f) {
                lastAttackedEntityHealth = currentTargetHealth;
                return;
            }
            
            // Prevent duplicate damage events within cooldown
            if (currentTime - lastDamageDealtTime < DAMAGE_COOLDOWN_MS) {
                lastAttackedEntityHealth = currentTargetHealth;
                return;
            }
            lastDamageDealtTime = currentTime;
            
            // Calculate damage as percentage of target's max health
            float targetMaxHealth = target.getMaxHealth();
            float damagePercentage = (damage / targetMaxHealth);
            if (damagePercentage > 1.0f) damagePercentage = 1.0f;
            
            // Send damage_dealt event
            JsonArray events = new JsonArray();
            JsonObject damageEvent = new JsonObject();
            damageEvent.addProperty("type", "damage_dealt");
            damageEvent.addProperty("amount", damage);
            damageEvent.addProperty("damage_percentage", damagePercentage);
            damageEvent.addProperty("target", target.getName());
            events.add(damageEvent);
            
            String botName = player.getName();
            System.out.println("[RewardListener] [TICK] Bot " + botName + " dealt " + damage + " damage (" + (damagePercentage * 100) + "%) to " + target.getName() + " (health: " + lastAttackedEntityHealth + " -> " + currentTargetHealth + ")");
            sendRewardEvents(events);
        }
        
        lastAttackedEntityHealth = currentTargetHealth;
    }
    
    /**
     * Tries to find the attacker by checking nearby entities
     */
    private String findAttacker(EntityPlayer player) {
        Minecraft mc = Minecraft.getMinecraft();
        if (mc.theWorld == null) {
            return null;
        }
        
        // Check nearby players (within 10 blocks)
        double maxDistance = 10.0;
        EntityPlayer closestEnemy = null;
        double closestDistance = Double.MAX_VALUE;
        
        for (Object obj : mc.theWorld.loadedEntityList) {
            if (obj instanceof EntityPlayer && !obj.equals(player)) {
                EntityPlayer enemy = (EntityPlayer) obj;
                if (enemy.isDead || enemy.getHealth() <= 0) {
                    continue;
                }
                
                double dx = enemy.posX - player.posX;
                double dy = enemy.posY - player.posY;
                double dz = enemy.posZ - player.posZ;
                double distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
                
                if (distance < maxDistance && distance < closestDistance) {
                    closestDistance = distance;
                    closestEnemy = enemy;
                }
            }
        }
        
        return closestEnemy != null ? closestEnemy.getName() : null;
    }
    
    /**
     * Normalizes yaw angle to -180 to 180 range
     */
    private float normalizeYaw(float yaw) {
        while (yaw > 180.0f) {
            yaw -= 360.0f;
        }
        while (yaw < -180.0f) {
            yaw += 360.0f;
        }
        return yaw;
    }
    
    /**
     * Normalizes yaw angle to -180 to 180 range (double version)
     */
    private double normalizeYaw(double yaw) {
        while (yaw > 180.0) {
            yaw -= 360.0;
        }
        while (yaw < -180.0) {
            yaw += 360.0;
        }
        return yaw;
    }
    
    /**
     * Sends reward events to the API
     */
    private void sendRewardEvents(JsonArray events) {
        try {
            Minecraft mc = Minecraft.getMinecraft();
            if (mc.thePlayer == null) {
                System.err.println("[RewardListener] Cannot send rewards: thePlayer is null");
                return;
            }
            
            if (events == null || events.size() == 0) {
                System.err.println("[RewardListener] Cannot send rewards: events array is empty");
                return;
            }
            
            String botName = mc.thePlayer.getName();
            
            // Build current state from player data
            JsonObject currentState = buildCurrentState(mc.thePlayer);
            
            // Build request JSON
            JsonObject request = new JsonObject();
            request.addProperty("bot_name", botName);
            request.add("events", events);
            request.add("current_state", currentState);
            
            String requestJson = request.toString();
            System.out.println("[RewardListener] Sending " + events.size() + " reward event(s) for " + botName + " to /add-reward/");
            
            // Send to API and check response
            String response = APIClient.postRequest("/add-reward/", requestJson);
            
            if (response == null) {
                // Log error - API request failed
                System.err.println("[RewardListener] FAILED to send reward events for " + botName + ". Response was null. Check API connection.");
                AIChatController.addChatLine("Reward API Error: Request failed for " + botName);
            } else {
                // Success - log for debugging
                System.out.println("[RewardListener] Successfully sent " + events.size() + " reward event(s) for " + botName + ". Response: " + response);
            }
        } catch (Exception e) {
            // Log error instead of silently failing
            System.err.println("[RewardListener] Exception sending reward events: " + e.getMessage());
            e.printStackTrace();
            AIChatController.addChatLine("Reward Exception: " + e.getMessage());
        }
    }
    
    /**
     * Builds current state JSON from player data
     */
    private JsonObject buildCurrentState(EntityPlayer player) {
        JsonObject state = new JsonObject();
        
        // Player data
        JsonObject playerData = new JsonObject();
        playerData.addProperty("health", player.getHealth());
        playerData.addProperty("x", player.posX);
        playerData.addProperty("y", player.posY);
        playerData.addProperty("z", player.posZ);
        playerData.addProperty("yaw", player.rotationYaw);
        playerData.addProperty("pitch", player.rotationPitch);
        
        // Get armor points
        int armorPoints = 0;
        if (player.inventory.armorInventory[3] != null) armorPoints += 2; // Helmet
        if (player.inventory.armorInventory[2] != null) armorPoints += 2; // Chestplate
        if (player.inventory.armorInventory[1] != null) armorPoints += 2; // Leggings
        if (player.inventory.armorInventory[0] != null) armorPoints += 2; // Boots
        playerData.addProperty("armor", armorPoints);
        
        state.add("player", playerData);
        
        return state;
    }
}

