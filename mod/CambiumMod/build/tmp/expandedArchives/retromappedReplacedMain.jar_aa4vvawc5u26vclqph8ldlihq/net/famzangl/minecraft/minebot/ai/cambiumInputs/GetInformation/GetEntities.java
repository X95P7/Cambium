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

        for (int i = 0; i < mc.field_71441_e.field_72996_f.size(); i++) {
            Entity entity = (Entity) mc.field_71441_e.field_72996_f.get(i);

            // Skip null entities and the player
            if (entity == null || entity == mc.field_71439_g) continue;

            // Determine if the entity is a projectile
            boolean isProjectile = entity instanceof EntityThrowable || entity instanceof EntityFishHook;

            // Check if the entity is a player
            boolean isPlayer = entity instanceof EntityPlayer;

            //Remove particles
            boolean relevent = entity instanceof EntityLivingBase || isProjectile || isPlayer; 
            if(!relevent) continue;
            // Get health and armor
            double health = entity instanceof EntityLivingBase ? ((EntityLivingBase) entity).func_110143_aJ() : 0;
            double armor = entity instanceof EntityLivingBase ? ((EntityLivingBase) entity).func_70658_aO() : 0;

            // Get hand item damage (or default to 1 if no item is held)
            double handDamage = 1;
            if (entity instanceof EntityLivingBase) {
                ItemStack heldItem = ((EntityLivingBase) entity).func_70694_bm();
                if (heldItem != null && heldItem.func_77973_b() instanceof ItemSword) {
                    handDamage = ((ItemSword) heldItem.func_77973_b()).func_150931_i();
                }
            }

            // Calculate relative position
            double relativeX = entity.field_70165_t - mc.field_71439_g.field_70165_t;
            double relativeY = entity.field_70163_u - mc.field_71439_g.field_70163_u;
            double relativeZ = entity.field_70161_v - mc.field_71439_g.field_70161_v;

            // Get velocity and facing direction
            double veloX = entity.field_70159_w;
            double veloY = entity.field_70181_x;
            double veloZ = entity.field_70179_y;
            float facingYaw = entity.field_70177_z;
            float facingPitch = entity.field_70125_A;

            // Add entity data to the list
            entityDataList.add(new EntityData(isProjectile, isPlayer, health, armor, handDamage, relativeX, relativeY, relativeZ, veloX, veloY, veloZ, facingYaw, facingPitch));
        }

        return entityDataList;
    }
}


