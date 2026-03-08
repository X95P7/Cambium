package net.famzangl.minecraft.minebot.ai.path.world;

import net.minecraft.init.Blocks;
import net.minecraft.util.BlockPos;

/**
 * This is a helper class that holds lots of block sets and helper functions to
 * check blocks for safety.
 * 
 * @author Michael Zangl
 */
public class BlockSets {

	public static final BlockSet EMPTY = new BlockSet(new int[0]);

	/**
	 * Blocks we can just walk over/next to without problems.
	 */
	public static final BlockSet SIMPLE_CUBE = new BlockSet(
			Blocks.field_150357_h,
			Blocks.field_150342_X,
			Blocks.field_150336_V,
			Blocks.field_150420_aW,
			Blocks.field_150414_aQ,
			Blocks.field_150435_aG,
			Blocks.field_150402_ci,
			Blocks.field_150365_q,
			Blocks.field_150347_e,
			Blocks.field_150462_ai,
			Blocks.field_150484_ah,
			Blocks.field_150482_ag,
			Blocks.field_150346_d,
			Blocks.field_150334_T,
			Blocks.field_150373_bw,
			Blocks.field_150475_bE,
			Blocks.field_150412_bA,
			// FIXME: Not a cube.
			Blocks.field_150458_ak, Blocks.field_150460_al, Blocks.field_150359_w, Blocks.field_150426_aN,
			Blocks.field_150349_c, Blocks.field_150340_R, Blocks.field_150352_o,
			Blocks.field_150405_ch, Blocks.field_150339_S, Blocks.field_150366_p,
			Blocks.field_150368_y, Blocks.field_150369_x, Blocks.field_150362_t,
			Blocks.field_150361_u, Blocks.field_150428_aP, Blocks.field_150470_am,
			Blocks.field_150374_bv, Blocks.field_150439_ay, Blocks.field_150364_r,
			Blocks.field_150363_s,
			Blocks.field_150440_ba,
			Blocks.field_150341_Y,
			Blocks.field_150391_bh,
			Blocks.field_150385_bj,
			Blocks.field_150424_aL,
			// Watch out, this cannot be broken easily !
			Blocks.field_150343_Z, Blocks.field_150403_cj, Blocks.field_150344_f, Blocks.field_150423_aK,
			Blocks.field_150371_ca, Blocks.field_150449_bY, Blocks.field_150419_aX,
			Blocks.field_150451_bX, Blocks.field_150379_bu, Blocks.field_150450_ax,
			Blocks.field_150322_A,
			Blocks.field_150433_aE,
			// FIXME: Not a cube.
			Blocks.field_150425_aM, Blocks.field_150399_cn,
			Blocks.field_150406_ce, Blocks.field_150348_b, Blocks.field_150417_aV,
			Blocks.field_150325_L);

	/**
	 * Blocks that fall down.
	 */
	public static final BlockSet FALLING = new BlockSet(Blocks.field_150351_n,
			Blocks.field_150354_m);

	public static final BlockSet AIR = new BlockSet(Blocks.field_150350_a);
	/**
	 * All stairs. It is no problem to walk on them.
	 */
	public static final BlockSet STAIRS = new BlockSet(Blocks.field_150400_ck,
			Blocks.field_150487_bG, Blocks.field_150389_bf, Blocks.field_150401_cl,
			Blocks.field_150481_bH, Blocks.field_150387_bl,
			Blocks.field_150476_ad, Blocks.field_150372_bz, Blocks.field_150485_bF,
			Blocks.field_150390_bg, Blocks.field_150446_ar, Blocks.field_150333_U,
			Blocks.field_150376_bx, Blocks.field_150370_cb);

	/**
	 * All rail blocks.
	 */
	public static final BlockSet RAILS = new BlockSet(Blocks.field_150318_D,
			Blocks.field_150319_E, Blocks.field_150448_aq, Blocks.field_150408_cc);

	/**
	 * Flowers and stuff like that
	 */
	private static final BlockSet explicitFootWalkableBlocks = new BlockSet(
			Blocks.field_150329_H, Blocks.field_150327_N, Blocks.field_150328_O,
			Blocks.field_150464_aj, Blocks.field_150459_bM, Blocks.field_150469_bN, Blocks.field_150393_bb,
			Blocks.field_150394_bc, Blocks.field_150404_cg, Blocks.field_150398_cm,
			Blocks.field_150337_Q, Blocks.field_150338_P, Blocks.field_150488_af,
			Blocks.field_150345_g, Blocks.field_150431_aC, Blocks.field_150388_bm,
			Blocks.field_150472_an, Blocks.field_150444_as, Blocks.field_150330_I).unionWith(RAILS);

	/**
	 * Torches.
	 */
	public static final BlockSet TORCH = new BlockSet(Blocks.field_150478_aa,
			Blocks.field_150429_aA);

	/**
	 * Blocks our head can walk though. Signs could be added here, but we stay
	 * away from them for now.
	 */
	public static final BlockSet HEAD_CAN_WALK_TRHOUGH = new BlockSet(
			Blocks.field_150350_a, Blocks.field_150398_cm, Blocks.field_150436_aH).unionWith(TORCH);

	public static final BlockSet FEET_CAN_WALK_THROUGH = explicitFootWalkableBlocks
			.unionWith(HEAD_CAN_WALK_TRHOUGH);

	public static final BlockSet FENCE = new BlockSet(Blocks.field_180407_aO,
			Blocks.field_180408_aP, Blocks.field_180404_aQ, Blocks.field_180403_aR,
			Blocks.field_180406_aS, Blocks.field_180405_aT,
			Blocks.field_150386_bk);

	public static final BlockSet WOODEN_DOR = new BlockSet(Blocks.field_180413_ao,
			Blocks.field_180414_ap, Blocks.field_180412_aq, Blocks.field_180411_ar,
			Blocks.field_180409_at, Blocks.field_180410_as);

	public static final BlockSet FENCE_GATE = new BlockSet(
			Blocks.field_180390_bo, Blocks.field_180391_bp,
			Blocks.field_180392_bq, Blocks.field_180386_br,
			Blocks.field_180385_bs, Blocks.field_180387_bt);

	private static final BlockSet explicitSafeSideBlocks = new BlockSet(
			Blocks.field_150467_bQ, Blocks.field_150463_bK, Blocks.field_150434_aF, Blocks.field_150436_aH,
			Blocks.field_150321_G, Blocks.field_150410_aZ, Blocks.field_150324_C, Blocks.field_150381_bn,
			Blocks.field_150392_bi, Blocks.field_150382_bo, Blocks.field_150395_bd, Blocks.field_150486_ae,
			Blocks.field_150447_bR, Blocks.field_150473_bD, Blocks.field_150479_bC,
			Blocks.field_150452_aw, Blocks.field_150456_au,
			Blocks.field_150471_bO, Blocks.field_150430_aB, Blocks.field_150418_aU)
			.unionWith(FENCE).unionWith(FENCE_GATE);

	/**
	 * Blocks that form a solid ground.
	 */
	public static final BlockSet SAFE_GROUND = SIMPLE_CUBE.unionWith(FALLING)
			.unionWith(STAIRS);

	public static final BlockSet SAFE_SIDE = explicitSafeSideBlocks
			.unionWith(SAFE_GROUND).unionWith(FEET_CAN_WALK_THROUGH)
			.unionWith(AIR);

	public static final BlockSet SAFE_CEILING = STAIRS
			.unionWith(FEET_CAN_WALK_THROUGH).unionWith(SIMPLE_CUBE)
			.unionWith(AIR).unionWith(new BlockSet(Blocks.field_150395_bd, Blocks.field_150434_aF));

	/**
	 * Blocks you need to destroy but that are then safe.
	 */
	public static final BlockSet SAFE_AFTER_DESTRUCTION = new BlockSet(
			Blocks.field_150395_bd, Blocks.field_150434_aF);

	/**
	 * Blocks that are considered indestructable and should be avoided.
	 */
	public static final BlockSet INDESTRUCTABLE = new BlockSet(Blocks.field_150357_h,
			Blocks.field_180401_cv, Blocks.field_150343_Z);

	/**
	 * All leaves. FIXME: Only consider leaves that do not decay as safe ground.
	 */
	public static final BlockSet LEAVES = new BlockSet(Blocks.field_150362_t,
			Blocks.field_150361_u);
	public static final BlockSet LOGS = new BlockSet(Blocks.field_150364_r, Blocks.field_150363_s);

	public static final BlockSet LOWER_SLABS;
	static {
		BlockSet lower = BlockSets.EMPTY;
		for (int i = 0; i < 8; i++) {
			lower = lower.unionWith(new BlockMetaSet(Blocks.field_150333_U, i));
			lower = lower.unionWith(new BlockMetaSet(Blocks.field_150376_bx, i));
		}
		lower = lower.unionWith(new BlockMetaSet(Blocks.field_180389_cP, 0));
		LOWER_SLABS = lower;
	}

	public static final BlockSet UPPER_SLABS;

	public static final BlockSet WATER = new BlockSet(Blocks.field_150355_j,
			Blocks.field_150358_i);

	public static final BlockSet TREE_BLOCKS = LOGS.unionWith(LEAVES);
	public static final BlockSet FURNACE = new BlockSet(Blocks.field_150460_al, Blocks.field_150470_am);

	static {
		BlockSet upper = BlockSets.EMPTY;
		for (int i = 0; i < 8; i++) {
			upper = upper.unionWith(new BlockMetaSet(Blocks.field_150333_U, i + 8));
			upper = upper
					.unionWith(new BlockMetaSet(Blocks.field_150376_bx, i + 8));
		}
		upper = upper.unionWith(new BlockMetaSet(Blocks.field_180389_cP, 8));
		UPPER_SLABS = upper;
	}

	public static boolean safeSideAround(WorldData world, int x, int y, int z) {
		return SAFE_SIDE.isAt(world, x + 1, y, z)
				&& SAFE_SIDE.isAt(world, x - 1, y, z)
				&& SAFE_SIDE.isAt(world, x, y, z + 1)
				&& SAFE_SIDE.isAt(world, x, y, z - 1);
	}

	public static boolean safeSideAround(WorldData world, BlockPos pos) {
		return safeSideAround(world, pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p());
	}

	public static boolean safeSideAndCeilingAround(WorldData world, int x,
			int y, int z) {
		return safeSideAround(world, x, y, z)
				&& SAFE_CEILING.isAt(world, x, y + 1, z);
	}

	public static boolean safeSideAndCeilingAround(WorldData world, BlockPos pos) {
		return safeSideAndCeilingAround(world, pos.func_177958_n(), pos.func_177956_o(),
				pos.func_177952_p());
	}

	private BlockSets() {
	}
}
