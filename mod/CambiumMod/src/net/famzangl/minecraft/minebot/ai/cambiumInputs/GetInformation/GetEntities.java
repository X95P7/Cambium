package net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation;

import java.util.ArrayList;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.EntityData;
import net.minecraft.client.Minecraft;
import net.minecraft.entity.Entity;
import net.minecraft.entity.EntityLivingBase;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraft.entity.projectile.EntityEgg;
import net.minecraft.entity.projectile.EntityFishHook;
import net.minecraft.entity.projectile.EntitySnowball;
import net.minecraft.entity.projectile.EntityThrowable;
import net.minecraft.item.ItemStack;
import net.minecraft.item.ItemSword;

public class GetEntities {
    private Minecraft mc;

    public GetEntities(AIHelper helper) {
        mc = helper.getMinecraft();
    }

    public ArrayList<EntityData> getEntities() {
        ArrayList<EntityData> entityDataList = new ArrayList<EntityData>();

        // Use a set to prevent duplicates if iterating multiple lists
        java.util.Set<Integer> processedIds = new java.util.HashSet<Integer>();

        // Priority 1: Check playerEntities first (more stable for players)
        for (Object pObj : mc.theWorld.playerEntities) {
            if (!(pObj instanceof EntityPlayer)) continue;
            EntityPlayer player = (EntityPlayer) pObj;
            if (player == mc.thePlayer || player.getEntityId() == mc.thePlayer.getEntityId()) continue;
            
            EntityData data = extractEntityData(player);
            if (data != null) {
                entityDataList.add(data);
                processedIds.add(player.getEntityId());
            }
        }

        // Priority 2: Check loadedEntityList for everything else (projectiles, NPCs, etc.)
        for (int i = 0; i < mc.theWorld.loadedEntityList.size(); i++) {
            Entity entity = (Entity) mc.theWorld.loadedEntityList.get(i);
            if (entity == null || entity == mc.thePlayer) continue;
            if (processedIds.contains(entity.getEntityId())) continue;

            boolean isProjectile = entity instanceof EntityThrowable || entity instanceof EntityFishHook;
            boolean isPlayer = entity instanceof EntityPlayer;
            boolean isLiving = entity instanceof EntityLivingBase; 
            
            if(!isLiving && !isProjectile && !isPlayer) continue;
            
            EntityData data = extractEntityData(entity);
            if (data != null) {
                entityDataList.add(data);
                processedIds.add(entity.getEntityId());
            }
        }

        // Sort entities by distance
        entityDataList.sort((a,b) -> {
            double distA = a.getRelativeX()*a.getRelativeX() + a.getRelativeY()*a.getRelativeY() + a.getRelativeZ()*a.getRelativeZ();
            double distB = b.getRelativeX()*b.getRelativeX() + b.getRelativeY()*b.getRelativeY() + b.getRelativeZ()*b.getRelativeZ();
            return Double.compare(distA, distB);
        });

        return entityDataList;
    }

    private EntityData extractEntityData(Entity entity) {
        try {
            boolean isProjectile = entity instanceof EntityThrowable || entity instanceof EntityFishHook;
            boolean isPlayer = entity instanceof EntityPlayer;
            
            String entityName = isPlayer ? entity.getName() : "";
            
            float health = 0;
            float armor = 0;
            if (entity instanceof EntityLivingBase) {
                health = ((EntityLivingBase) entity).getHealth();
                armor = ((EntityLivingBase) entity).getTotalArmorValue();
            }

            double relativeX = entity.posX - mc.thePlayer.posX;
            double relativeY = entity.posY - mc.thePlayer.posY;
            double relativeZ = entity.posZ - mc.thePlayer.posZ;

            double veloX = entity.motionX;
            double veloY = entity.motionY;
            double veloZ = entity.motionZ;

            float facingYaw = entity.rotationYaw;
            float facingPitch = entity.rotationPitch;

            int handDamage = 0;
            if (entity instanceof EntityLivingBase) {
                ItemStack heldItem = ((EntityLivingBase) entity).getHeldItem();
                if (heldItem != null && (heldItem.getItem() instanceof ItemSword || heldItem.getItem() instanceof net.minecraft.item.ItemTool)) {
                    handDamage = 5; // Simplified damage value
                }
            }
            
            return new EntityData(isProjectile, isPlayer, entityName, health, armor, handDamage, relativeX, relativeY, relativeZ, veloX, veloY, veloZ, facingYaw, facingPitch);
        } catch (Exception e) {
            // Log the exception if necessary
            return null;
        }
    }
}
