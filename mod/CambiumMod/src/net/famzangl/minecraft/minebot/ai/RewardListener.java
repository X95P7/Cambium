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
    private static final long DAMAGE_COOLDOWN_MS = 25; // 25ms cooldown between damage events
    
    // Track last attack to detect damage dealt
    private Entity lastAttackedEntity = null;
    private float lastAttackedEntityHealth = -1.0f;
    private long lastDamageDealtTime = 0;
    
    // Track aim checking
    private long lastAimCheckTime = 0;
    private static final long AIM_CHECK_INTERVAL_MS = 100; // Check aim every 100ms
    private int consecutiveAimChecks = 0; // Require sustained aim (2+ checks) to reduce sweep-through rewards
    private static final int AIM_SUSTAINED_THRESHOLD = 2; // Must be on target for 2 checks (~200ms) before rewarding
    
    // Track damage detection via tick
    private long lastDamageCheckTime = 0;
    private static final long DAMAGE_CHECK_INTERVAL_MS = 50; // Check damage every 50ms
    private boolean isAttacking = false; // Track if player is currently attacking
    private long lastAttackStartTime = 0;
    
    @SubscribeEvent
    public void onLivingHurt(LivingHurtEvent event) {
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
            
            long currentTime = System.currentTimeMillis();
            if (currentTime - lastDamageTakenTime < DAMAGE_COOLDOWN_MS) {
                return;
            }
            lastDamageTakenTime = currentTime;
            
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
            
            lastHealth = player.getHealth() - damage;
        }
        
        // Check if our bot dealt damage to another entity
        if (source.getEntity() instanceof EntityPlayer && source.getEntity().equals(mc.thePlayer)) {
            EntityPlayer attacker = (EntityPlayer) source.getEntity();
            String botName = attacker.getName();
            
            long currentTime = System.currentTimeMillis();
            if (currentTime - lastDamageDealtTime < DAMAGE_COOLDOWN_MS) {
                return;
            }
            
            if (entity instanceof EntityPlayer) {
                lastDamageDealtTime = currentTime;
                
                EntityPlayer target = (EntityPlayer) entity;
                float targetMaxHealth = target.getMaxHealth();
                float damagePercentage = Math.min(damage / targetMaxHealth, 1.0f);
                
                JsonArray events = new JsonArray();
                JsonObject damageEvent = new JsonObject();
                damageEvent.addProperty("type", "damage_dealt");
                damageEvent.addProperty("amount", damage);
                damageEvent.addProperty("damage_percentage", damagePercentage);
                damageEvent.addProperty("target", entity.getName());
                events.add(damageEvent);
                
                System.out.println("[RewardListener] [EVENT] Bot " + botName + " dealt " + damage + " damage (" + (damagePercentage * 100) + "%) to " + entity.getName());
                sendRewardEvents(events);
                
                lastAttackedEntity = entity;
                lastAttackedEntityHealth = target.getHealth();
            }
        }
    }
    
    @SubscribeEvent
    public void onAttackEntity(AttackEntityEvent event) {
        if (event.entity.worldObj.isRemote && event.entity instanceof EntityPlayer) {
            EntityPlayer player = (EntityPlayer) event.entity;
            Minecraft mc = Minecraft.getMinecraft();
            
            if (player.equals(mc.thePlayer) && event.target instanceof EntityPlayer) {
                lastAttackedEntity = event.target;
                lastAttackedEntityHealth = ((EntityPlayer) event.target).getHealth();
                isAttacking = true;
                lastAttackStartTime = System.currentTimeMillis();
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
        EntityPlayer closestEnemy = findClosestEnemy(player, mc, 50.0);
        double closestDistance = Double.MAX_VALUE;
        if (closestEnemy != null) {
            double dx = closestEnemy.posX - player.posX;
            double dy = closestEnemy.posY - player.posY;
            double dz = closestEnemy.posZ - player.posZ;
            closestDistance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        }
        
        if (closestEnemy != null) {
            // Calculate angle to enemy - use BODY CENTER (posY + 0.9) not feet for melee hit accuracy
            double targetY = closestEnemy.posY + 0.9;
            double dx = closestEnemy.posX - player.posX;
            double dy = targetY - (player.posY + player.getEyeHeight());
            double dz = closestEnemy.posZ - player.posZ;
            
            double targetYaw = Math.atan2(-dx, dz) * 180.0 / Math.PI;
            double horizontalDist = Math.sqrt(dx * dx + dz * dz);
            double targetPitch = -Math.atan2(dy, horizontalDist) * 180.0 / Math.PI;
            
            float playerYaw = player.rotationYaw;
            float playerPitch = player.rotationPitch;
            
            playerYaw = normalizeYaw(playerYaw);
            targetYaw = normalizeYaw(targetYaw);
            
            double yawDiff = Math.abs(normalizeYaw(playerYaw - targetYaw));
            double pitchDiff = Math.abs(playerPitch - targetPitch);
            double maxAngle = Math.max(yawDiff, pitchDiff);
            
            // Calculate aim score (percentage-based)
            double aimScore = 0.0;
            if (maxAngle < 5) {
                aimScore = 1.0;
            } else if (maxAngle < 10) {
                aimScore = 0.8;
            } else if (maxAngle < 20) {
                aimScore = 0.5;
            } else if (maxAngle < 45) {
                aimScore = 0.2;
            }
            
            if (aimScore > 0) {
                consecutiveAimChecks++;
                if (consecutiveAimChecks >= AIM_SUSTAINED_THRESHOLD) {
                    JsonArray events = new JsonArray();
                    JsonObject aimEvent = new JsonObject();
                    aimEvent.addProperty("type", "good_aim");
                    aimEvent.addProperty("amount", aimScore);
                    aimEvent.addProperty("yaw_diff", yawDiff);
                    aimEvent.addProperty("pitch_diff", pitchDiff);
                    aimEvent.addProperty("distance", closestDistance);
                    events.add(aimEvent);
                    sendRewardEvents(events);
                }
            } else {
                consecutiveAimChecks = 0;
            }
        } else {
            consecutiveAimChecks = 0;
        }
    }
    
    /**
     * Checks if bot took damage by monitoring health changes
     */
    private void checkDamageTaken(EntityPlayer player, long currentTime) {
        float currentHealth = player.getHealth();
        
        if (lastHealth < 0) {
            lastHealth = currentHealth;
            return;
        }
        
        if (currentHealth < lastHealth) {
            float damage = lastHealth - currentHealth;
            
            if (damage < 0.1f) {
                lastHealth = currentHealth;
                return;
            }
            
            if (currentTime - lastDamageTakenTime < DAMAGE_COOLDOWN_MS) {
                lastHealth = currentHealth;
                return;
            }
            lastDamageTakenTime = currentTime;
            
            JsonArray events = new JsonArray();
            JsonObject damageEvent = new JsonObject();
            damageEvent.addProperty("type", "damage_taken");
            damageEvent.addProperty("amount", damage);
            
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
     * Checks if bot dealt damage by monitoring the closest enemy's health.
     * In a 1v1 arena, any health drop on the enemy = damage we dealt.
     * No swing/attack detection needed — just continuous health monitoring.
     */
    private void checkDamageDealt(EntityPlayer player, Minecraft mc, long currentTime) {
        // Always track the closest living enemy (1v1 arena assumption)
        EntityPlayer target = findClosestEnemy(player, mc, 50.0);
        
        if (target == null) {
            if (lastAttackedEntity != null) {
                lastAttackedEntity = null;
                lastAttackedEntityHealth = -1.0f;
                isAttacking = false;
            }
            return;
        }
        
        // If target changed, reset health tracking
        if (lastAttackedEntity == null || !target.equals(lastAttackedEntity)) {
            lastAttackedEntity = target;
            lastAttackedEntityHealth = target.getHealth();
            return;
        }
        
        float currentTargetHealth = target.getHealth();
        boolean targetDead = target.isDead || currentTargetHealth <= 0;
        
        if (lastAttackedEntityHealth < 0) {
            lastAttackedEntityHealth = targetDead ? -1.0f : currentTargetHealth;
            if (targetDead) {
                lastAttackedEntity = null;
                isAttacking = false;
            }
            return;
        }
        
        // Any health decrease on the enemy = damage we dealt (1v1 assumption)
        if (currentTargetHealth < lastAttackedEntityHealth) {
            float damage = lastAttackedEntityHealth - currentTargetHealth;
            
            if (damage >= 0.1f && (currentTime - lastDamageDealtTime >= DAMAGE_COOLDOWN_MS)) {
                lastDamageDealtTime = currentTime;
                
                float targetMaxHealth = target.getMaxHealth();
                float damagePercentage = Math.min(damage / targetMaxHealth, 1.0f);
                
                JsonArray events = new JsonArray();
                JsonObject damageEvent = new JsonObject();
                damageEvent.addProperty("type", "damage_dealt");
                damageEvent.addProperty("amount", damage);
                damageEvent.addProperty("damage_percentage", damagePercentage);
                damageEvent.addProperty("target", target.getName());
                events.add(damageEvent);
                
                System.out.println("[RewardListener] [TICK] Bot " + player.getName() + " dealt " + damage + " damage (" + (damagePercentage * 100) + "%) to " + target.getName() + " (health: " + lastAttackedEntityHealth + " -> " + currentTargetHealth + ")");
                sendRewardEvents(events);
            }
        }
        
        lastAttackedEntityHealth = currentTargetHealth;
        
        if (targetDead) {
            lastAttackedEntity = null;
            lastAttackedEntityHealth = -1.0f;
            isAttacking = false;
        }
    }
    
    /**
     * Finds the closest living enemy player within maxDist blocks.
     */
    private EntityPlayer findClosestEnemy(EntityPlayer player, Minecraft mc, double maxDist) {
        if (mc.theWorld == null) return null;
        EntityPlayer closest = null;
        double best = Double.MAX_VALUE;
        for (Object obj : mc.theWorld.loadedEntityList) {
            if (obj instanceof EntityPlayer && !obj.equals(player)) {
                EntityPlayer enemy = (EntityPlayer) obj;
                if (enemy.isDead || enemy.getHealth() <= 0) continue;
                double dx = enemy.posX - player.posX;
                double dy = enemy.posY - player.posY;
                double dz = enemy.posZ - player.posZ;
                double d = Math.sqrt(dx * dx + dy * dy + dz * dz);
                if (d < maxDist && d < best) {
                    best = d;
                    closest = enemy;
                }
            }
        }
        return closest;
    }

    /**
     * Tries to find the attacker by checking nearby entities
     */
    private String findAttacker(EntityPlayer player) {
        Minecraft mc = Minecraft.getMinecraft();
        if (mc.theWorld == null) {
            return null;
        }
        
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
    
    private float normalizeYaw(float yaw) {
        while (yaw > 180.0f) {
            yaw -= 360.0f;
        }
        while (yaw < -180.0f) {
            yaw += 360.0f;
        }
        return yaw;
    }
    
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
            
            JsonObject currentState = buildCurrentState(mc.thePlayer);
            
            JsonObject request = new JsonObject();
            request.addProperty("bot_name", botName);
            request.add("events", events);
            request.add("current_state", currentState);
            
            String requestJson = request.toString();
            System.out.println("[RewardListener] Sending " + events.size() + " reward event(s) for " + botName + " to /add-reward/");
            
            String response = APIClient.postRequest("/add-reward/", requestJson);
            
            if (response == null) {
                System.err.println("[RewardListener] FAILED to send reward events for " + botName + ". Response was null. Check API connection.");
                AIChatController.addChatLine("Reward API Error: Request failed for " + botName);
            } else {
                System.out.println("[RewardListener] Successfully sent " + events.size() + " reward event(s) for " + botName + ". Response: " + response);
            }
        } catch (Exception e) {
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
        
        JsonObject playerData = new JsonObject();
        playerData.addProperty("health", player.getHealth());
        playerData.addProperty("x", player.posX);
        playerData.addProperty("y", player.posY);
        playerData.addProperty("z", player.posZ);
        playerData.addProperty("yaw", player.rotationYaw);
        playerData.addProperty("pitch", player.rotationPitch);
        
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
