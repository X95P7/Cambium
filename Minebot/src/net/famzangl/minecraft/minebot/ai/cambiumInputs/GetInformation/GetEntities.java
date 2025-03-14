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

        for (int i = 0; i < mc.theWorld.loadedEntityList.size(); i++) {
            Entity entity = (Entity) mc.theWorld.loadedEntityList.get(i);

            // Skip null entities and the player
            if (entity == null || entity == mc.thePlayer) continue;

            // Determine if the entity is a projectile
            boolean isProjectile = entity instanceof EntityThrowable || entity instanceof EntityFishHook;

            // Check if the entity is a player
            boolean isPlayer = entity instanceof EntityPlayer;

            //Remove particles
            boolean relevent = entity instanceof EntityLivingBase || isProjectile || isPlayer; 
            if(!relevent) continue;
            // Get health and armor
            double health = entity instanceof EntityLivingBase ? ((EntityLivingBase) entity).getHealth() : 0;
            double armor = entity instanceof EntityLivingBase ? ((EntityLivingBase) entity).getTotalArmorValue() : 0;

            // Get hand item damage (or default to 1 if no item is held)
            double handDamage = 1;
            if (entity instanceof EntityLivingBase) {
                ItemStack heldItem = ((EntityLivingBase) entity).getHeldItem();
                if (heldItem != null && heldItem.getItem() instanceof ItemSword) {
                    handDamage = ((ItemSword) heldItem.getItem()).getDamageVsEntity();
                }
            }

            // Calculate relative position
            double relativeX = entity.posX - mc.thePlayer.posX;
            double relativeY = entity.posY - mc.thePlayer.posY;
            double relativeZ = entity.posZ - mc.thePlayer.posZ;

            // Get velocity and facing direction
            double veloX = entity.motionX;
            double veloY = entity.motionY;
            double veloZ = entity.motionZ;
            float facingYaw = entity.rotationYaw;
            float facingPitch = entity.rotationPitch;

            // Add entity data to the list
            entityDataList.add(new EntityData(isProjectile, isPlayer, health, armor, handDamage, relativeX, relativeY, relativeZ, veloX, veloY, veloZ, facingYaw, facingPitch));
        }

        return entityDataList;
    }
}


