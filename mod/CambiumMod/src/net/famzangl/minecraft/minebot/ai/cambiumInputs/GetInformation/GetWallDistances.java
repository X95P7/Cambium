package net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation;

import java.util.ArrayList;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.BlockData;
import net.minecraft.client.Minecraft;
import net.minecraft.util.MovingObjectPosition;
import net.minecraft.util.Vec3;

/**
 * Casts 8 horizontal rays in cardinal directions (N, NE, E, SE, S, SW, W, NW)
 * to detect wall distances. Much cheaper than the full sphere raytrace.
 * Returns exactly 8 BlockData entries with the distance to the nearest wall
 * in each direction.
 */
public class GetWallDistances {
    private final AIHelper helper;
    private static final double MAX_RAY_DISTANCE = 50.0;  // Increased detection range (was 5.0)

    // 8 cardinal directions at eye level (yaw angles in degrees)
    // 0=South(+Z), 90=West(-X), 180=North(-Z), 270=East(+X)
    private static final double[] DIRECTION_ANGLES = {
        180.0,  // N  (0)
        225.0,  // NE (1) 
        270.0,  // E  (2)
        315.0,  // SE (3)
          0.0,  // S  (4)
         45.0,  // SW (5)
         90.0,  // W  (6)
        135.0   // NW (7)
    };

    private static final String[] DIRECTION_NAMES = {
        "N", "NE", "E", "SE", "S", "SW", "W", "NW"
    };

    public GetWallDistances(AIHelper helper) {
        this.helper = helper;
    }

    /**
     * Cast 8 horizontal rays and return distances to walls.
     * Always returns exactly 8 BlockData entries (one per direction).
     * If no wall is hit, distance is set to MAX_RAY_DISTANCE.
     */
    public ArrayList<BlockData> getWallDistances() {
        Minecraft mc = helper.getMinecraft();
        ArrayList<BlockData> results = new ArrayList<BlockData>();

        if (mc.thePlayer == null || mc.theWorld == null) {
            // Return 8 entries with max distance
            for (int i = 0; i < 8; i++) {
                results.add(new BlockData(0, 0, 0, MAX_RAY_DISTANCE, false, DIRECTION_NAMES[i]));
            }
            return results;
        }

        Vec3 eyePos = mc.thePlayer.getPositionEyes(1.0F);

        for (int i = 0; i < DIRECTION_ANGLES.length; i++) {
            double angle = Math.toRadians(DIRECTION_ANGLES[i]);
            
            // Horizontal ray (pitch = 0)
            double dx = -Math.sin(angle);
            double dz = Math.cos(angle);

            Vec3 end = eyePos.addVector(
                dx * MAX_RAY_DISTANCE,
                0,  // horizontal only
                dz * MAX_RAY_DISTANCE
            );

            MovingObjectPosition result = mc.theWorld.rayTraceBlocks(eyePos, end, false, false, false);

            double distance = MAX_RAY_DISTANCE;
            boolean hitWall = false;
            int hitX = 0, hitY = 0, hitZ = 0;

            if (result != null && result.typeOfHit == MovingObjectPosition.MovingObjectType.BLOCK) {
                distance = result.hitVec.distanceTo(eyePos);
                hitWall = true;
                hitX = result.getBlockPos().getX() - (int) mc.thePlayer.posX;
                hitY = result.getBlockPos().getY() - (int) mc.thePlayer.posY;
                hitZ = result.getBlockPos().getZ() - (int) mc.thePlayer.posZ;
            }

            results.add(new BlockData(hitX, hitY, hitZ, distance, hitWall, DIRECTION_NAMES[i]));
        }

        return results;
    }
}
