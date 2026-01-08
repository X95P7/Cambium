package com.example.tickfreeze;

import net.minecraft.entity.Entity;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraft.entity.projectile.EntityEgg;
import net.minecraft.entity.projectile.EntityFishHook;
import net.minecraft.entity.projectile.EntitySnowball;
import net.minecraft.entity.projectile.EntityThrowable;
import net.minecraftforge.event.entity.EntityJoinWorldEvent;
import net.minecraftforge.event.entity.living.LivingEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Server-side handler that adds knockback when projectiles (egg, enderpearl, fishing rod, snowball) hit players.
 */
public class ProjectileKnockbackHandler {
    
    // Track projectiles and their last hit times to prevent spam
    private static final Map<UUID, Long> projectileLastHit = new HashMap<UUID, Long>();
    private static final long HIT_COOLDOWN = 100; // 100ms cooldown between hits from same projectile
    
    // Knockback strength for different projectiles
    private static final double EGG_KNOCKBACK = 0.4;
    private static final double SNOWBALL_KNOCKBACK = 0.4;
    private static final double ENDERPEARL_KNOCKBACK = 0.3;
    private static final double FISHING_ROD_KNOCKBACK = 0.5;
    
    /**
     * Checks if a throwable entity is an ender pearl by checking its item
     */
    private boolean isEnderPearl(Entity entity) {
        if (entity instanceof EntityThrowable) {
            EntityThrowable throwable = (EntityThrowable) entity;
            // In 1.8.9, we can check the thrower's item or use reflection
            // For now, we'll use a simpler approach - check class name or skip
            return entity.getClass().getSimpleName().equals("EntityEnderPearl");
        }
        return false;
    }
    
    @SubscribeEvent
    public void onEntityJoinWorld(EntityJoinWorldEvent event) {
        // Track projectiles when they spawn
        Entity entity = event.entity;
        if (isProjectile(entity)) {
            // Initialize tracking for this projectile
            projectileLastHit.put(entity.getUniqueID(), 0L);
        }
    }
    
    @SubscribeEvent
    public void onLivingUpdate(LivingEvent.LivingUpdateEvent event) {
        // Only run on server side
        if (event.entity.worldObj.isRemote) {
            return;
        }
        
        // Check if this is a player
        if (!(event.entity instanceof EntityPlayer)) {
            return;
        }
        
        EntityPlayer player = (EntityPlayer) event.entity;
        
        // Check for nearby projectiles
        for (Object obj : player.worldObj.loadedEntityList) {
            if (!(obj instanceof Entity)) {
                continue;
            }
            
            Entity entity = (Entity) obj;
            
            // Skip if not a projectile we care about
            if (!isProjectile(entity)) {
                continue;
            }
            
            // Skip if projectile is dead or removed
            if (entity.isDead || entity.isInvisible()) {
                continue;
            }
            
            // Check if projectile is close enough to player (collision detection)
            double distance = player.getDistanceToEntity(entity);
            
            // Collision radius: player bounding box + projectile bounding box
            double collisionRadius = player.width / 2.0 + entity.width / 2.0 + 0.1;
            
            if (distance < collisionRadius) {
                // Check cooldown
                UUID projectileId = entity.getUniqueID();
                long currentTime = System.currentTimeMillis();
                Long lastHitTime = projectileLastHit.get(projectileId);
                
                if (lastHitTime == null || (currentTime - lastHitTime) > HIT_COOLDOWN) {
                    // Apply knockback
                    applyKnockback(player, entity);
                    projectileLastHit.put(projectileId, currentTime);
                    
                    // Remove projectile after hit (except enderpearl which teleports)
                    if (!isEnderPearl(entity)) {
                        entity.setDead();
                    }
                }
            }
        }
    }
    
    /**
     * Checks if an entity is a projectile we want to add knockback for
     */
    private boolean isProjectile(Entity entity) {
        return entity instanceof EntityEgg ||
               entity instanceof EntitySnowball ||
               isEnderPearl(entity) ||
               entity instanceof EntityFishHook;
    }
    
    /**
     * Applies knockback to a player when hit by a projectile
     */
    private void applyKnockback(EntityPlayer player, Entity projectile) {
        // Calculate knockback direction (from projectile to player)
        double dx = player.posX - projectile.posX;
        double dy = player.posY - projectile.posY;
        double dz = player.posZ - projectile.posZ;
        
        // Normalize direction
        double distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (distance < 0.01) {
            // Too close, use projectile velocity instead
            dx = projectile.motionX;
            dy = projectile.motionY;
            dz = projectile.motionZ;
            distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        }
        
        if (distance < 0.01) {
            // No velocity, use default direction
            dx = 0;
            dy = 0.1;
            dz = 0;
            distance = 0.1;
        }
        
        // Normalize
        dx /= distance;
        dy /= distance;
        dz /= distance;
        
        // Get knockback strength based on projectile type
        double knockbackStrength = getKnockbackStrength(projectile);
        
        // Apply knockback velocity
        player.motionX += dx * knockbackStrength;
        player.motionY += dy * knockbackStrength + 0.1; // Add slight upward component
        player.motionZ += dz * knockbackStrength;
        
        // Clamp vertical velocity to prevent excessive upward knockback
        if (player.motionY > 0.4) {
            player.motionY = 0.4;
        }
        
        // Mark player as having been hit (for invulnerability frames if needed)
        player.hurtResistantTime = 0; // Allow immediate knockback
        
        // Send velocity update to client
        player.velocityChanged = true;
    }
    
    /**
     * Gets the knockback strength for a specific projectile type
     */
    private double getKnockbackStrength(Entity projectile) {
        if (projectile instanceof EntityEgg) {
            return EGG_KNOCKBACK;
        } else if (projectile instanceof EntitySnowball) {
            return SNOWBALL_KNOCKBACK;
        } else if (isEnderPearl(projectile)) {
            return ENDERPEARL_KNOCKBACK;
        } else if (projectile instanceof EntityFishHook) {
            return FISHING_ROD_KNOCKBACK;
        }
        return 0.3; // Default
    }
}

