package net.famzangl.minecraft.minebot.ai.strategy.cambium;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.ItemFilter;
import net.famzangl.minecraft.minebot.ai.strategy.FaceInteractStrategy;
import net.minecraft.client.settings.GameSettings;
import net.minecraft.client.settings.KeyBinding;
import net.minecraft.entity.Entity;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraft.item.ItemStack;
import net.minecraft.item.ItemSword;
import net.minecraft.util.MovingObjectPosition;
import net.minecraft.util.MovingObjectPosition.MovingObjectType;

import com.google.common.base.Predicate;

/**
 * Basic PvP strategy that finds and attacks nearby players.
 * 
 * @author Cambium
 */
public class PvPStrategy extends FaceInteractStrategy {
    
    private int tickCounter = 0;
    private GameSettings gameSettings;
    private KeyBinding attackItemKey;
    private int originalKeyCode;
    private final int TEMP_KEY_CODE = 502;
    private boolean keyRemapped = false;
    
    @Override
    protected TickResult onGameTick(AIHelper helper) {
        // Initialize key remapping on first tick
        if (!keyRemapped) {
            gameSettings = helper.getMinecraft().gameSettings;
            attackItemKey = gameSettings.keyBindAttack;
            originalKeyCode = attackItemKey.getKeyCodeDefault();
            attackItemKey.setKeyCode(TEMP_KEY_CODE);
            KeyBinding.resetKeyBindingArrayAndHash();
            keyRemapped = true;
        }
        
        // Call parent tick logic (handles movement and facing)
        TickResult result = super.onGameTick(helper);
        
        // Attack every other tick (every 2 ticks)
        tickCounter++;
        if (tickCounter % 2 == 0) {
            // Check if we're looking at a player
            MovingObjectPosition over = helper.getObjectMouseOver();
            if (over != null && 
                over.typeOfHit == MovingObjectType.ENTITY && 
                over.entityHit instanceof EntityPlayer &&
                over.entityHit != helper.getMinecraft().thePlayer &&
                !over.entityHit.isDead &&
                ((EntityPlayer) over.entityHit).getHealth() > 0) {
                
                // Select sword if available
                helper.selectCurrentItem(new ItemFilter() {
                    @Override
                    public boolean matches(ItemStack itemStack) {
                        return itemStack != null && itemStack.getItem() instanceof ItemSword;
                    }
                });
                
                // Attack using the same method as LeftClickStrategy
                KeyBinding.onTick(TEMP_KEY_CODE);
            }
        }
        
        return result;
    }
    
    @Override
    protected void onDeactivate(AIHelper helper) {
        // Restore original key code when strategy is deactivated
        if (keyRemapped && attackItemKey != null) {
            attackItemKey.setKeyCode(originalKeyCode);
            KeyBinding.resetKeyBindingArrayAndHash();
            keyRemapped = false;
        }
    }
    
    @Override
    protected Predicate<Entity> entitiesToInteract(AIHelper helper) {
        return new Predicate<Entity>() {
            @Override
            public boolean apply(Entity entity) {
                // Only target players, not ourselves, and they must be alive
                if (entity instanceof EntityPlayer && 
                    entity != helper.getMinecraft().thePlayer &&
                    !entity.isDead &&
                    ((EntityPlayer) entity).getHealth() > 0) {
                    return true;
                }
                return false;
            }
        };
    }
    
    @Override
    protected Predicate<Entity> entitiesToFace(AIHelper helper) {
        return entitiesToInteract(helper);
    }
    
    @Override
    protected boolean doInteractWithCurrent(Entity entityHit, AIHelper helper) {
        // Select sword if available when we're looking at a player
        if (entityHit instanceof EntityPlayer && 
            entityHit != helper.getMinecraft().thePlayer &&
            !entityHit.isDead &&
            ((EntityPlayer) entityHit).getHealth() > 0) {
            
            helper.selectCurrentItem(new ItemFilter() {
                @Override
                public boolean matches(ItemStack itemStack) {
                    return itemStack != null && itemStack.getItem() instanceof ItemSword;
                }
            });
            
            return true;
        }
        return false;
    }
    
    @Override
    protected void doInteract(Entity entityHit, AIHelper helper) {
        // Attack is handled in onGameTick now
    }
    
    @Override
    public String getDescription(AIHelper helper) {
        Entity target = getCurrentTarget(helper);
        if (target != null) {
            return "PvP: Attacking " + ((EntityPlayer) target).getName();
        }
        return "PvP: Searching for players...";
    }
    
    private Entity getCurrentTarget(AIHelper helper) {
        MovingObjectPosition over = helper.getObjectMouseOver();
        if (over != null && 
            over.typeOfHit == MovingObjectType.ENTITY && 
            over.entityHit instanceof EntityPlayer) {
            return over.entityHit;
        }
        return null;
    }
}

