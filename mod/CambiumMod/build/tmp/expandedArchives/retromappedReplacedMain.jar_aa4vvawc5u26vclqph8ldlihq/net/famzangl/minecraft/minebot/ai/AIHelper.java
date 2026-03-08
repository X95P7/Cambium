/*******************************************************************************
 * This file is part of Minebot.
 *
 * Minebot is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Minebot is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Minebot.  If not, see <http://www.gnu.org/licenses/>.
 *******************************************************************************/
package net.famzangl.minecraft.minebot.ai;

import java.io.File;
import java.util.HashMap;
import java.util.List;
import java.util.Random;

import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.input.KeyboardInputController;
import net.famzangl.minecraft.minebot.ai.input.KeyboardInputController.KeyType;
import net.famzangl.minecraft.minebot.ai.net.NetworkHelper;
import net.famzangl.minecraft.minebot.ai.path.world.BlockBounds;
import net.famzangl.minecraft.minebot.ai.path.world.Pos;
import net.famzangl.minecraft.minebot.ai.path.world.WorldData;
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;
import net.famzangl.minecraft.minebot.ai.task.BlockHalf;
import net.famzangl.minecraft.minebot.ai.tools.ToolRater;
import net.famzangl.minecraft.minebot.ai.utils.RandUtils;
import net.famzangl.minecraft.minebot.build.BuildManager;
import net.famzangl.minecraft.minebot.map.MapReader;
import net.famzangl.minecraft.minebot.settings.MinebotSettings;
import net.famzangl.minecraft.minebot.settings.SaferuleSettings;
import net.famzangl.minecraft.minebot.stats.StatsManager;
import net.minecraft.block.Block;
import net.minecraft.block.BlockFence;
import net.minecraft.block.BlockFenceGate;
import net.minecraft.block.BlockSlab;
import net.minecraft.block.BlockWall;
import net.minecraft.block.state.IBlockState;
import net.minecraft.client.Minecraft;
import net.minecraft.entity.Entity;
import net.minecraft.item.ItemStack;
import net.minecraft.util.BlockPos;
import net.minecraft.util.EnumFacing;
import net.minecraft.util.MathHelper;
import net.minecraft.util.MovementInput;
import net.minecraft.util.MovingObjectPosition;
import net.minecraft.util.MovingObjectPosition.MovingObjectType;
import net.minecraft.util.Vec3;
import net.minecraft.world.chunk.Chunk;
import net.minecraft.world.chunk.storage.ExtendedBlockStorage;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.logging.log4j.Marker;
import org.apache.logging.log4j.MarkerManager;

import com.google.common.base.Predicate;

import net.minecraft.util.MovingObjectPosition.MovingObjectType;
/**
 * Lots and lots of helpful methods to control the current player. This contains
 * the current marked positions ({@link #pos1}, {@link #pos2}), fast methods to
 * access/check minecraft blocks ({@link #getBlockId(BlockPos)}), many lists of
 * different block types/presets useful for filtering, methods to control the
 * player ({@link #face(double, double, double)}, {@link #overrideUseItem()}),
 * some methods to get the player state ({@link #isAlive()},
 * {@link #getPlayerPosition()}) and some to simplify block handling (
 * {@link #getSignDirection(IBlockState)})
 * 
 * @author michael
 * 
 */
public abstract class AIHelper {
	private static final Marker MARKER_FACING = MarkerManager
			.getMarker("facing");
	private static final Logger LOGGER = LogManager.getLogger(AIHelper.class);
	private static final double SNEAK_OFFSET = .2;
	private static final double WALK_PER_STEP = 4.3 / 20;
	private static final double MIN_DISTANCE_ERROR = 0.05;
	private static final float MAX_PITCH_CHANGE;
	private static final float MAX_YAW_CHANGE;
	private static final boolean ALLOW_TOP_OF_WORLD_HIT;
	
	static {
		SaferuleSettings settings = MinebotSettings.getSettings().getSaferules();
		MAX_PITCH_CHANGE = settings.getMaxPitchChangeDegrees();
		MAX_YAW_CHANGE = settings.getMaxYawChangeDegrees();
		ALLOW_TOP_OF_WORLD_HIT = settings.isAllowTopOfWorldHit();
	}
	
	private static Minecraft mc = Minecraft.func_71410_x();
	/**
	 * A world that never gets a delta applied to it.
	 */
	private static WorldData minecraftWorld;
	private final Random rand = new Random();

	public final BuildManager buildManager = new BuildManager();
	private boolean objectMouseOverInvalidated;

	protected BlockPos pos1 = null;
	protected BlockPos pos2 = null;

	private MovementInput resetMovementInput;
	
	private HashMap<KeyType, KeyboardInputController> keys = new HashMap<KeyType, KeyboardInputController>();
	
	protected boolean doUngrab;

	protected MapReader activeMapReader;
	
	private final StatsManager stats = new StatsManager();

	public AIHelper() {
		for (KeyType key : KeyType.values()) {
			keys.put(key, new KeyboardInputController(mc, key));
		}
	}
	
	/**
	 * A random number in a range, that does not exactly hit the sides.
	 * 
	 * @param minY
	 * @param maxY
	 * @return
	 */
	private static double randBetweenNice(double minY, double maxY) {
		return maxY - minY < 0.1 ? (maxY + minY) / 2 : randBetween(minY + 0.03,
				maxY - 0.03);
	}

	private static double randBetween(double a, double b) {
		return RandUtils.getBetween(a, b);
	}

	protected void invalidateChunkCache() {
		if (minecraftWorld == null
				|| mc.field_71441_e != minecraftWorld.getBackingWorld()) {
			if (mc.field_71441_e == null) {
				minecraftWorld = null;
			} else {
				minecraftWorld = new WorldData(
						mc.field_71441_e, mc.field_71439_g);
			}
		}
		if (minecraftWorld != null) {
			minecraftWorld.invalidateChunkCache();
		}
	}

	public Minecraft getMinecraft() {
		return mc;
	}

	public static File getMinebotDir() {
		File dir = new File(mc.field_71412_D, "minebot");
		if (!dir.exists()) {
			dir.mkdir();
		}
		return dir;
	}

	/**
	 * Gets the pos1 marker.
	 * 
	 * @return The marker or <code>null</code> if it is unset.
	 */
	public BlockPos getPos1() {
		return pos1;
	}

	/**
	 * Gets the pos2 marker.
	 * 
	 * @return The marker or <code>null</code> if it is unset.
	 */
	public BlockPos getPos2() {
		return pos2;
	}

	/**
	 * Sets the pos1 or pos2 marker.
	 * 
	 * @param pos
	 *            The new position.
	 * @param isPos2
	 */
	public void setPosition(BlockPos pos, boolean isPos2) {
		int posIndex;
		if (isPos2) {
			pos2 = pos;
			posIndex = 2;
		} else {
			pos1 = pos;
			posIndex = 1;
		}
		AIChatController.addChatLine("Set position" + posIndex + " to " + pos);
	}

	/**
	 * Needs to be called whenever the player moved and the block faced might
	 * have changed.
	 */
	public void invalidateObjectMouseOver() {
		objectMouseOverInvalidated = true;
	}

	/**
	 * Gets the object the player is currently facing. This should always be
	 * used instead of the Minecraft version, since it handles player movement
	 * updates in the same game tick.
	 * 
	 * @return
	 */
	public MovingObjectPosition getObjectMouseOver() {
		if (objectMouseOverInvalidated) {
			objectMouseOverInvalidated = false;
			mc.field_71460_t.func_78473_a(1.0F);
		}
		return mc.field_71476_x;
	}

	/**
	 * Gets the block at that position.
	 * 
	 * @param pos
	 * @return
	 */
	public Block getBlock(BlockPos pos) {
		// TODO: Warn that no delta is used.
		return getBlock(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p());
	}

	/**
	 * Gets the block at that position.
	 * 
	 * @param x
	 * @param y
	 * @param z
	 * @return The block.
	 */
	public Block getBlock(int x, int y, int z) {
		// TODO: Warn that no delta is used.
		return mc.field_71441_e.func_180495_p(new BlockPos(x, y, z)).func_177230_c();
	}

	public WorldData getWorld() {
		return minecraftWorld;
	}

	/**
	 * Gets the required angular change to face a given point.
	 * @param x
	 * @param y
	 * @param z
	 * @return
	 */
	public double getRequiredAngularChangeTo(double x, double y, double z) {
		final double d0 = x - mc.field_71439_g.field_70165_t;
		final double d1 = z - mc.field_71439_g.field_70161_v;
		final double d2 = y - mc.field_71439_g.field_70163_u - mc.field_71439_g.func_70047_e();
		final double d3 = d0 * d0 + d2 * d2 + d1 * d1;

		if (d3 < 2.500000277905201E-7D) {
			return 0;
		}
		
		Vec3 playerLook = mc.field_71439_g.func_70040_Z().func_72432_b();
		return Math.acos(playerLook.func_72430_b(new Vec3(d0, d1, d2).func_72432_b()));
	}
	
	public boolean isFacing(Vec3 vec) {
		return isFacing(vec.field_72450_a, vec.field_72448_b, vec.field_72449_c);
	}

	public boolean isFacing(double x, double y, double z) {
		return face(x, y, z, 0, 0);
	}

	public boolean face(Vec3 vec) {
		return face(vec.field_72450_a, vec.field_72448_b, vec.field_72449_c);
	}

	/**
	 * Faces an exact position in space.
	 * 
	 * @param x
	 * @param y
	 * @param z
	 */
	public boolean face(double x, double y, double z) {
		return face(x, y, z, 1, 1);
	}

	private boolean face(double x, double y, double z, float yawInfluence,
			float pitchInfluence) {

		LOGGER.trace(MARKER_FACING, "facing " + x + "," + y + "," + z
				+ " using influence: " + yawInfluence + ";" + pitchInfluence);
		final double d0 = x - mc.field_71439_g.field_70165_t;
		final double d1 = z - mc.field_71439_g.field_70161_v;
		final double d2 = y - mc.field_71439_g.field_70163_u - mc.field_71439_g.func_70047_e();
		final double d3 = d0 * d0 + d2 * d2 + d1 * d1;

		if (d3 >= 2.500000277905201E-7D) {
			final float rotationYaw = mc.field_71439_g.field_70177_z;
			final float rotationPitch = mc.field_71439_g.field_70125_A;

			final float yaw = (float) (Math.atan2(d1, d0) * 180.0D / Math.PI) - 90.0F;
			final float pitch = (float) -(Math.atan2(d2,
					Math.sqrt(d0 * d0 + d1 * d1)) * 180.0D / Math.PI);
			float yawChange = closestRotation(yaw - rotationYaw);
			float pitchChange = pitch - rotationPitch;
			assert -Math.PI <= yawChange && yawChange <= Math.PI;
			float yawClamp = Math.min(Math.abs(MAX_YAW_CHANGE / yawChange), 1);
			float pitchClamp = Math.min(
					Math.abs(MAX_PITCH_CHANGE / pitchChange), 1);
			float clamp = Math.min(yawClamp, pitchClamp);
			if (yawInfluence <= 0 && pitchInfluence <= 0) {
				// only test, do not set
				return Math.abs(yawChange) < .01 && Math.abs(pitchChange) < .01;
			}

			yawInfluence = Math.min(yawInfluence, clamp);
			pitchInfluence = Math.min(pitchInfluence, clamp);
			// TODO: Make this linear?

			mc.field_71439_g.func_70082_c(yawChange / 0.15f * yawInfluence,
					-pitchChange / 0.15f * pitchInfluence);
			invalidateObjectMouseOver();

			LOGGER.trace(MARKER_FACING, "facing clamped at " + clamp
					+ ", new influence:  " + yawInfluence + ";"
					+ pitchInfluence + ", done: " + (clamp > .999));

			return clamp > .999;
		}
		return true;
	}

	private float closestRotation(float f) {
		float halfRot = 180;
		float fullRot = halfRot * 2;
		return (((f + halfRot) % fullRot + fullRot) % fullRot) - halfRot;
	}

	private float fullRotations(float yaw) {
		return (float) (((int) (yaw / (Math.PI * 2))) * Math.PI * 2);
	}

	public boolean isFacingBlock(BlockPos pos) {
		return isFacingBlock(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p());
	}

	/**
	 * Checks if the player is currently facing the block so that it can be
	 * interacted with.
	 * 
	 * @param x
	 * @param y
	 * @param z
	 * @return <code>true</code> if it is facing the Block.
	 */
	public boolean isFacingBlock(int x, int y, int z) {
		final MovingObjectPosition o = getObjectMouseOver();
		return o != null
				&& o.field_72313_a == MovingObjectType.BLOCK
				&& new BlockPos(x, y, z).equals(o.func_178782_a())
				&& (y < 255 || allowTopOfWorldHit() || o.field_178784_b != EnumFacing.UP);
	}

	private boolean allowTopOfWorldHit() {
		return ALLOW_TOP_OF_WORLD_HIT;
	}

	public boolean isFacingBlock(BlockPos pos, EnumFacing blockSide,
			BlockHalf half) {
		return isFacingBlock(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p(), blockSide,
				half);
	}

	/**
	 * Checks if the player is facing a specific side of the block.
	 * 
	 * @param x
	 * @param y
	 * @param z
	 * @param blockSide
	 *            The side of the block.
	 * @param half
	 *            Can restrict the check to the upper or lower half of the side
	 *            (not useful for top/bottom)
	 * @return <code>true</code> if the player faces the block.
	 */
	public boolean isFacingBlock(int x, int y, int z, EnumFacing blockSide,
			BlockHalf half) {
		if (!isFacingBlock(x, y, z, blockSide)) {
			return false;
		} else {
			final double fy = getObjectMouseOver().field_72307_f.field_72448_b - y;
			return half != BlockHalf.LOWER_HALF && fy > .5
					|| half != BlockHalf.UPPER_HALF && fy <= .5;
		}
	}

	public boolean isFacingBlock(BlockPos pos, EnumFacing side) {
		return isFacingBlock(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p(), side);
	}

	/**
	 * Checks if the player is facing a specific side of the block.
	 * 
	 * @param x
	 * @param y
	 * @param z
	 * @param blockSide
	 *            The side of the block as game integer.
	 * @return <code>true</code> if the player faces the block.
	 */
	public boolean isFacingBlock(int x, int y, int z, EnumFacing side) {
		final MovingObjectPosition o = getObjectMouseOver();
		return isFacingBlock(x, y, z) && o.field_178784_b == side;
	}

	public boolean isStandingOn(BlockPos pos) {
		return isStandingOn(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p());
	}

	/**
	 * Are the feet standing on that block?
	 * 
	 * @param x
	 * @param y
	 * @param z
	 * @return
	 */
	public boolean isStandingOn(int x, int y, int z) {
		// boolean isFence = blockIsOneOf(getBlock(x, y - 1, z),
		// FenceBuildTask.BLOCKS);
		return Math.abs(x + 0.5 - mc.field_71439_g.field_70165_t) < 0.2
				&& Math.abs(z + 0.5 - mc.field_71439_g.field_70161_v) < 0.2
				&& Math.abs(mc.field_71439_g.func_174813_aQ().field_72338_b - y) < 0.52;
	}

	public double realBlockTopY(BlockPos pos) {
		return realBlockTopY(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p());
	}

	/**
	 * The real top y cord of the block we stand on. Watch out: Minecraft blocks
	 * do not always provide the right bounds with it's block objects.
	 * 
	 * @param x
	 * @param y
	 * @param z
	 * @return
	 */
	public double realBlockTopY(int x, int y, int z) {
		final Block block = getBlock(x, y - 1, z);
		// Fence bounds are not exposed...
		double maxY;
		if (block instanceof BlockFence || block instanceof BlockFenceGate
				|| block instanceof BlockWall) {
			maxY = 1.5;
		} else if (block instanceof BlockSlab) {
			final int blockMetadata = getWorld().getBlockIdWithMeta(x, y, z) & 0xf;
			maxY = (blockMetadata & 0x8) == 0 ? 0.5 : 1;
		} else {
			maxY = block.func_149669_A();
		}

		return y - 1 + maxY;
	}

	/**
	 * Get the current position the player is at.
	 * 
	 * @return The position.
	 */
	public BlockPos getPlayerPosition() {
		return getWorld().getPlayerPosition();
	}

	/*
	 * public void moveTo(int x, int y, int z) { face(x + .5, mc.thePlayer.posY,
	 * z + .5); MovementInput i = new MovementInput(); i.moveForward = 0.8f;
	 * overrideMovement(i); }
	 */

	/**
	 * Checks if an item is on the hotbar.
	 * 
	 * @param f
	 *            The item to search
	 * @return <code>true</code> if it is selectable.
	 */
	public boolean canSelectItem(ItemFilter f) {
		for (int i = 0; i < 9; ++i) {
			if (f.matches(mc.field_71439_g.field_71071_by.func_70301_a(i))) {
				return true;
			}
		}
		return false;
	}

	/**
	 * Selects an item.
	 * 
	 * @param f
	 *            The item to search for.
	 * @return <code>true</code> if the player is now holding that item.
	 */
	public boolean selectCurrentItem(ItemFilter f) {
		if (f.matches(mc.field_71439_g.field_71071_by.func_70448_g())) {
			return true;
		}
		for (int i = 0; i < 9; ++i) {
			if (f.matches(mc.field_71439_g.field_71071_by.func_70301_a(i))) {
				mc.field_71439_g.field_71071_by.field_70461_c = i;
				return true;
			}
		}
		return false;
	}
	
	public static class ToolRaterResult {
		private final int bestSlot;
		private final float bestSlotRating;
		
		public ToolRaterResult(int bestSlot, float bestSlotRating) {
			super();
			this.bestSlot = bestSlot;
			this.bestSlotRating = bestSlotRating;
		}

		public int getBestSlot() {
			return bestSlot;
		}

		public float getBestSlotRating() {
			return bestSlotRating;
		}

		public boolean wasSuccessful() {
			return bestSlotRating > 0;
		}

		@Override
		public int hashCode() {
			final int prime = 31;
			int result = 1;
			result = prime * result + bestSlot;
			result = prime * result + Float.floatToIntBits(bestSlotRating);
			return result;
		}

		@Override
		public boolean equals(Object obj) {
			if (this == obj)
				return true;
			if (obj == null)
				return false;
			if (getClass() != obj.getClass())
				return false;
			ToolRaterResult other = (ToolRaterResult) obj;
			if (bestSlot != other.bestSlot)
				return false;
			if (Float.floatToIntBits(bestSlotRating) != Float
					.floatToIntBits(other.bestSlotRating))
				return false;
			return true;
		}

		@Override
		public String toString() {
			return "ToolRaterResult [bestSlot=" + bestSlot
					+ ", bestSlotRating=" + bestSlotRating + "]";
		}
	}

	/**
	 * Selects a good tool for mining the given Block.
	 * 
	 * @param pos
	 */
	public ToolRaterResult selectToolFor(final BlockPos pos) {
		ToolRater toolRater = MinebotSettings.getSettings().getToolRater();
		return selectToolFor(pos, toolRater);
	}

	public void setHotbarTo(int slot){
		mc.field_71439_g.field_71071_by.field_70461_c = slot;
	}

	public void faceDirection(float yaw, float pitch) {
		mc.field_71439_g.func_70082_c(yaw, pitch);
	}

	/**
	 * Selects a good tool for mining the given Block.
	 * 
	 * @param pos
	 * @param ToolRater
	 *            the tool rater that rates the tool.
	 */
	public ToolRaterResult selectToolFor(final BlockPos pos, ToolRater rater) {
		ToolRaterResult res = searchToolFor(pos, rater);
		mc.field_71439_g.field_71071_by.field_70461_c = res.getBestSlot();
		return res;
	}
	
	public ToolRaterResult searchToolFor(final BlockPos pos, ToolRater rater) {
		int bestRatingSlot = mc.field_71439_g.field_71071_by.field_70461_c;
		if (bestRatingSlot < 0 || bestRatingSlot >= 9) {
			bestRatingSlot = 0;
		}
		int block = pos == null ? -1 : getWorld().getBlockIdWithMeta(pos);
		float bestRating = rater.rateTool(
				mc.field_71439_g.field_71071_by.func_70301_a(bestRatingSlot), block);
		for (int i = 0; i < 9; ++i) {
			float rating = rater.rateTool(
					mc.field_71439_g.field_71071_by.func_70301_a(i), block);
			if (rating > bestRating) {
				bestRating = rating;
				bestRatingSlot = i;
			}
		}

		return new ToolRaterResult(bestRatingSlot, bestRating);
	}

	/**
	 * Faces a block and destroys it if possible.
	 * 
	 * @param pos
	 *            the Position of that block.
	 */
	public void faceAndDestroy(final BlockPos pos) {
		if (!isFacingBlock(pos)) {
			faceBlock(pos);
		}

		if (isFacingBlock(pos)) {
			selectToolFor(pos);
			overrideAttack();
			stats.markIntentionalBlockBreak(pos);
		}
	}

	public void faceAndDestroyWithHangingBlock(final BlockPos pos) {
		faceAndDestroy(pos);
		if (!isFacingBlock(pos)) {
			// Check if there is a block hanging here.
			for (EnumFacing d : EnumFacing.values()) {
				BlockPos offseted = pos.func_177972_a(d);
				if (isFacingBlock(offseted)) {
					BlockPos hanging = getWorld().getHangingOnBlock(offseted);
					if (hanging != null && hanging.equals(pos)) {
						overrideAttack();
					}
				}
			}
		}
	}

	/**
	 * Faces a block.
	 * 
	 * @param pos
	 * @return
	 */
	public boolean faceBlock(BlockPos pos) {
		return face(getWorld().getBlockBounds(pos).random(pos, .95));
	}

	/**
	 * Face the side of a block.
	 * 
	 * @param pos
	 * @param sideToFace
	 * @return
	 */
	public boolean faceSideOf(BlockPos pos, EnumFacing sideToFace) {
		BlockBounds bounds = getWorld().getBlockBounds(pos);
		return face(bounds.onlySide(sideToFace).random(pos, 0.8));
	}

	/**
	 * Advanced version to face a specific side of a block.
	 * 
	 * @param x
	 * @param y
	 * @param z
	 * @param sideToFace
	 *            To restrict facing on a given side. Can be <code>null</code>
	 *            to disable.
	 * @param minY
	 *            Limits the Y coordinate that is faced.
	 * @param maxY
	 *            Limits the Y coordinate that is faced.
	 * @param centerX
	 * @param centerZ
	 * @param xzdir
	 *            The direction the xz restriction affects.
	 */
	public void faceSideOf(BlockPos pos, EnumFacing sideToFace, double minY,
			double maxY, double centerX, double centerZ, EnumFacing xzdir) {
		// System.out.println("x = " + x + " y=" + y + " z=" + z + " dir="
		// + sideToFace);
		BlockBounds bounds = getWorld().getBlockBounds(pos);
		BlockBounds faceArea = bounds.clampY(minY, maxY).onlySide(sideToFace);
		LOGGER.trace(MARKER_FACING, "Facing: " + faceArea);
		face(faceArea.random(pos, .9));

		// minY = Math.max(minY, block.getBlockBoundsMinY());
		// maxY = Math.min(maxY, block.getBlockBoundsMaxY());
		// double faceY = randBetweenNice(minY, maxY);
		// double faceX, faceZ;
		//
		// if (xzdir == EnumFacing.EAST) {
		// faceX = randBetween(Math.max(block.getBlockBoundsMinX(), centerX),
		// block.getBlockBoundsMaxX());
		// faceZ = centerZ;
		// } else if (xzdir == EnumFacing.WEST) {
		// faceX = randBetween(block.getBlockBoundsMinX(),
		// Math.min(block.getBlockBoundsMaxX(), centerX));
		// faceZ = centerZ;
		// } else if (xzdir == EnumFacing.SOUTH) {
		// faceZ = randBetween(Math.max(block.getBlockBoundsMinZ(), centerZ),
		// block.getBlockBoundsMaxZ());
		// faceX = centerX;
		// } else if (xzdir == EnumFacing.NORTH) {
		// faceZ = randBetween(block.getBlockBoundsMinZ(),
		// Math.min(block.getBlockBoundsMaxZ(), centerZ));
		// faceX = centerX;
		// } else {
		// faceX = randBetweenNice(block.getBlockBoundsMinX(),
		// block.getBlockBoundsMaxX());
		// faceZ = randBetweenNice(block.getBlockBoundsMinZ(),
		// block.getBlockBoundsMaxZ());
		// }
		// switch (sideToFace) {
		// case UP:
		// faceY = block.getBlockBoundsMaxY();
		// break;
		// case DOWN:
		// faceY = block.getBlockBoundsMinY();
		// break;
		// case EAST:
		// faceX = block.getBlockBoundsMaxX();
		// break;
		// case WEST:
		// faceX = block.getBlockBoundsMinX();
		// break;
		// case SOUTH:
		// faceZ = block.getBlockBoundsMaxZ();
		// break;
		// case NORTH:
		// faceZ = block.getBlockBoundsMinZ();
		// break;
		// default:
		// break;
		// }
		// face(faceX + pos.getX(), faceY + pos.getY(), faceZ + pos.getZ());
	}

	/**
	 * Checks if an item is in the main inventory.
	 * 
	 * @param itemFiler
	 * @return
	 */
	public boolean hasItemInInvetory(ItemFilter itemFiler) {
		for (final ItemStack s : mc.field_71439_g.field_71071_by.field_70462_a) {
			if (itemFiler.matches(s)) {
				return true;
			}
		}
		return false;
	}

	/**
	 * overrides the keyboard input in the next game tick.
	 * 
	 * @param i
	 */
	public void overrideMovement(MovementInput i) {
		if (resetMovementInput == null) {
			resetMovementInput = mc.field_71439_g.field_71158_b;
		}
		mc.field_71439_g.field_71158_b = i;
	}

	/**
	 * Presses the use item key in the next game tick.
	 */
	public void overrideUseItem() {
		overrideKey(KeyType.USE);
	}

	/**
	 * Presses the attack key in the next game tick.
	 */
	public void overrideAttack() {
		if (mc.field_71439_g.func_71039_bw()) {
			LOGGER.warn("WARNING: Player is currently using an item, but attack was requested.");
		}
		overrideKey(KeyType.ATTACK);
	}

	/**
	 * Presses the sneak key in the next game step.
	 */
	public void overrideSneak() {
		overrideKey(KeyType.SNEAK);
	}

	/**
	 * Presses the sneak key in the next game step.
	 */
	public void overrideSprint() {
		overrideKey(KeyType.SPRINT);
	}

	private void overrideKey(KeyType type) {
		keys.get(type).overridePressed();
	}

	/**
	 * Restore all inputs to the default minecraft inputs.
	 */
	protected void resetAllInputs() {
		if (resetMovementInput != null) {
			mc.field_71439_g.field_71158_b = resetMovementInput;
			resetMovementInput = null;
		}
	}
	
	protected void keyboardPostTick() {
		for (KeyboardInputController k : keys.values()) {
			k.doTick();
		}
	}

	protected boolean userTookOver() {
		for (KeyboardInputController key : keys.values()) {
			if (key.wasPressedByUser()) {
				return true;
			}
		}
		return false;
	}

	/**
	 * Ungrabs the mouse.
	 */
	public void ungrab() {
		doUngrab = true;
	}

	/**
	 * Gets a list of entities in a given distance filtered with a filter.
	 * 
	 * @param dist
	 * @param selector
	 * @return
	 */
	@SuppressWarnings("unchecked")
	public List<Entity> getEntities(int dist, Predicate<Entity> selector) {
		return mc.field_71441_e.func_175674_a(
				mc.func_175606_aa(),
				mc.func_175606_aa().func_174813_aQ()
						.func_72321_a(-dist, -dist, -dist)
						.func_72321_a(dist, dist, dist).func_72314_b(1, 1, 1), selector);
	}

	/**
	 * Gets the closest entity limited by a given distance.
	 * 
	 * @param dist
	 * @param selector
	 * @return
	 * @see #getEntities(int, Predicate<Entity>)
	 */
	public Entity getClosestEntity(int dist, Predicate<Entity> selector) {
		final List<Entity> entities = getEntities(dist, selector);

		double mindist = Double.MAX_VALUE;
		Entity found = null;
		for (final Entity e : entities) {
			final double mydist = e.func_70068_e(mc.field_71439_g);
			if (mydist < mindist) {
				found = e;
				mindist = mydist;
			}
		}

		return found;
	}

	/**
	 * Sneak while standing on that block facing that direction.
	 * 
	 * @param pos
	 *            The position of which we should sneak to the side.
	 * @param inDirection
	 *            The side to sneak at.
	 * @return <code>true</code> on arrival.
	 */
	public boolean sneakFrom(BlockPos pos, EnumFacing inDirection) {
		return sneakFrom(pos, inDirection, true);
	}

	/**
	 * Sneak while standing on that block.
	 * 
	 * @param pos
	 *            The position of which we should sneak to the side.
	 * @param inDirection
	 *            The side to sneak at.
	 * @param face
	 *            Should we face that position?
	 * @return <code>true</code> on arrival.
	 */
	public boolean sneakFrom(BlockPos pos, EnumFacing inDirection, boolean face) {
		BlockBounds bounds = getWorld().getBlockBounds(pos);
		double destX = pos.func_177958_n() + .5;
		double destZ = pos.func_177952_p() + .5;
		switch (inDirection) {
		case EAST:
			destX = pos.func_177958_n() + bounds.getMaxX() + SNEAK_OFFSET;
			break;
		case WEST:
			destX = pos.func_177958_n() + bounds.getMinX() - SNEAK_OFFSET;
			break;
		case SOUTH:
			destZ = pos.func_177952_p() + bounds.getMaxZ() + SNEAK_OFFSET;
			break;
		case NORTH:
			destZ = pos.func_177952_p() + bounds.getMinZ() - SNEAK_OFFSET;
			break;
		default:
			throw new IllegalArgumentException("Cannot handle " + inDirection);
		}
		return walkTowards(destX, destZ, false, face);
	}

	/**
	 * Walks towards a given point. Automatically slows down at the point
	 * 
	 * @param x
	 * @param z
	 * @param jump
	 *            If we should jump.
	 * @return <code>true</code> after arrival.
	 */
	public boolean walkTowards(double x, double z, boolean jump) {
		return walkTowards(x, z, jump, true);
	}

	public boolean walkTowards(double x, double z, boolean jump, boolean face) {
		final double dx = x - mc.field_71439_g.field_70165_t;
		final double dz = z - mc.field_71439_g.field_70161_v;
		final double distTo = Math.sqrt(dx * dx + dz * dz);
		boolean arrived = distTo > MIN_DISTANCE_ERROR;
		if (arrived) {
			if (face) {
				face(x, mc.field_71439_g.func_70047_e() + mc.field_71439_g.field_70163_u, z, 1,
						.1f);
			}
			double speed = 1;
			if (distTo < 4 * WALK_PER_STEP) {
				speed = Math.max(distTo / WALK_PER_STEP / 4, 0.1);
			}
			final double yaw = mc.field_71439_g.field_70177_z / 180 * Math.PI;
			final double lookX = -Math.sin(yaw);
			final double lookZ = Math.cos(yaw);
			final double dlength = Math.sqrt(dx * dx + dz * dz);
			final double same = (lookX * dx + lookZ * dz) / dlength;
			final double strafe = (lookZ * dx - lookX * dz) / dlength;
			LOGGER.trace(MARKER_FACING, "look: " + lookX + "," + lookZ
					+ "; d = " + dx + "," + dz + "; walk: " + same + ","
					+ strafe);
			final MovementInput movement = new MovementInput();
			movement.field_78900_b = (float) (speed * same);
			movement.field_78902_a = (float) (speed * strafe);
			movement.field_78901_c = jump;
			overrideMovement(movement);
			if (distTo < 0.5 || mc.field_71439_g.func_70051_ag() && distTo < 0.8) {
				overrideSneak();
			} else if (distTo > 6) {
				overrideSprint();
			}
			return false;
		} else {
			return true;
		}
	}

	public boolean arrivedAt(double x, double z) {
		final double dx = x - mc.field_71439_g.field_70165_t;
		final double dz = z - mc.field_71439_g.field_70161_v;
		final double distTo = Math.sqrt(dx * dx + dz * dz);
		return distTo <= MIN_DISTANCE_ERROR;
	}

	public boolean isJumping() {
		return !mc.field_71439_g.field_70122_E;
	}

	/**
	 * Gets the horizontal direction we look at.
	 * 
	 * @return
	 */
	public EnumFacing getLookDirection() {
		switch (MathHelper
				.func_76128_c(getMinecraft().field_71439_g.field_70177_z / 360 * 4 + .5) & 3) {
		case 1:
			return EnumFacing.WEST;
		case 2:
			return EnumFacing.NORTH;
		case 3:
			return EnumFacing.EAST;
		default:
			return EnumFacing.SOUTH;
		}
	}

	/**
	 * See if the player has not died (=> the game over screen would be
	 * displayed).
	 * 
	 * @return <code>true</code> if it is alive.
	 */
	public boolean isAlive() {
		return mc.field_71439_g != null && mc.field_71439_g.func_110143_aJ() > 0.0F;
	}

	public void respawn() {
		if (!isAlive()) {
			mc.field_71439_g.func_71004_bE();
			mc.func_147108_a(null);
		}
	}

	/**
	 * Converts an valid x/z pair to a direction if possible.
	 * 
	 * @param x
	 * @param z
	 * @return
	 */
	public static EnumFacing getDirectionForXZ(int x, int z) {
		if (x != 0 || z != 0) {
			for (final EnumFacing d : EnumFacing.values()) {
				if (d.func_82601_c() == x && d.func_82599_e() == z) {
					return d;
				}
			}
		}
		throw new IllegalArgumentException("Cannot convert to direction: " + x
				+ " " + z);
	}

	public static EnumFacing getDirectionFor(BlockPos delta) {
		for (final EnumFacing d : EnumFacing.values()) {
			if (Pos.fromDir(d).equals(delta)) {
				return d;
			}
		}
		throw new IllegalArgumentException("Cannot convert to direction: "
				+ delta);
	}

	// TODO: Move this to WorldData
	public int getLightAt(BlockPos pos) {
		final Chunk chunk = mc.field_71441_e.func_72964_e(
				pos.func_177958_n() >> 4, pos.func_177952_p() >> 4);
		final ExtendedBlockStorage storage = chunk.func_76587_i()[pos
				.func_177956_o() >> 4];
		if (storage == null) {
			return 0;
		} else {
			return storage.func_76674_d(pos.func_177958_n() & 15,
					pos.func_177956_o() & 15, pos.func_177952_p() & 15);
		}
	}

	public void setActiveMapReader(MapReader activeMapReader) {
		if (this.activeMapReader != null) {
			this.activeMapReader.onStop();
		}
		this.activeMapReader = activeMapReader;
	}

	public abstract AIStrategy getResumeStrategy();

	public abstract NetworkHelper getNetworkHelper();

	public MapReader getActiveMapReader() {
		return activeMapReader;
	}
	
	public StatsManager getStats() {
		return stats;
	}

}
