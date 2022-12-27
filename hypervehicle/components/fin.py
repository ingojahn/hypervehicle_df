import numpy as np
from scipy.optimize import bisect
from gdtk.geom.vector3 import Vector3
from gdtk.geom.path import Line, Polyline
from gdtk.geom.surface import CoonsPatch
from hypervehicle.components.component import Component
from hypervehicle.components.constants import FIN_COMPONENT
from hypervehicle.geometry import (
    OffsetPatchFunction,
    SubRangedPath,
    ElipsePath,
    ArcLengthParameterizedPath,
    TrailingEdgePatch,
    TrailingEdgePath,
    RotatedPatch,
    MeanLeadingEdgePatchFunction,
    OffsetPathFunction,
    GeometricMeanPathFunction,
)


class Fin(Component):
    componenttype = FIN_COMPONENT

    def __init__(self, params: dict, verbosity: int = 1) -> None:
        super().__init__(params, verbosity)

    def generate_patches(self):
        # Initialise
        temp_fin_patch_dict = {}

        # Extract geometric properties
        p0 = self.params["p0"]
        p1 = self.params["p1"]
        p2 = self.params["p2"]
        p3 = self.params["p3"]
        fin_thickness = self.params["FIN_THICKNESS"]
        fin_angle = self.params["FIN_ANGLE"]
        fin_thickness_function_top = self.params["FIN_TOP_THICKNESS_FUNC"]
        fin_thickness_function_bot = self.params["FIN_BOTTOM_THICKNESS_FUNC"]
        leading_edge_width_function = self.params["FIN_LEADING_EDGE_FUNC"]

        p1p2 = Line(p1, p2)
        p2p3 = Line(p2, p3)
        p1p3 = Polyline(segments=[p1p2, p2p3])

        if self.verbosity > 1:
            print("    Creating fin planform.")

        p0p1 = Line(p0, p1)
        fin_patch = CoonsPatch(
            north=Line(p1, p2),
            east=Line(p3, p2),
            south=Line(p0, p3),
            west=Line(p0, p1),
        )
        flipped_fin_patch = CoonsPatch(
            north=Line(p3, p2),
            east=Line(p1, p2),
            south=Line(p0, p1),
            west=Line(p0, p3),
        )

        if self.verbosity > 1:
            print("    Adding thickness to fin.")
        top_patch = OffsetPatchFunction(flipped_fin_patch, fin_thickness_function_top)
        bot_patch = OffsetPatchFunction(fin_patch, fin_thickness_function_bot)
        temp_fin_patch_dict["top_patch"] = top_patch
        temp_fin_patch_dict["bot_patch"] = bot_patch

        if self.verbosity > 1:
            print("    Adding Leading Edge to fin.")

        top_edge_path = OffsetPathFunction(p1p3, fin_thickness_function_top)
        bot_edge_path = OffsetPathFunction(p1p3, fin_thickness_function_bot)
        mean_path = GeometricMeanPathFunction(top_edge_path, bot_edge_path)

        # Find Locations
        fun_B1 = lambda t: p1p3(t).x - p2.x
        t_B1 = bisect(fun_B1, 0.0, 1.0)
        t_B2 = 1

        LE_top_patch = [np.nan, np.nan, np.nan]
        LE_bot_patch = [np.nan, np.nan, np.nan]

        # Eliptical LE
        LE_top_patch[0] = MeanLeadingEdgePatchFunction(
            mean_path,
            top_edge_path,
            LE_width_function=leading_edge_width_function,
            t0=0.0,
            t1=t_B1,
            side="top",
        )
        LE_top_patch[1] = MeanLeadingEdgePatchFunction(
            mean_path,
            top_edge_path,
            LE_width_function=leading_edge_width_function,
            t0=t_B1,
            t1=t_B2,
            side="top",
        )

        LE_bot_patch[0] = MeanLeadingEdgePatchFunction(
            mean_path,
            bot_edge_path,
            LE_width_function=leading_edge_width_function,
            t0=0.0,
            t1=t_B1,
            side="bot",
        )
        LE_bot_patch[1] = MeanLeadingEdgePatchFunction(
            mean_path,
            bot_edge_path,
            LE_width_function=leading_edge_width_function,
            t0=t_B1,
            t1=t_B2,
            side="bot",
        )

        temp_fin_patch_dict["LE_top_patch_0"] = LE_top_patch[0]
        temp_fin_patch_dict["LE_top_patch_1"] = LE_top_patch[1]
        temp_fin_patch_dict["LE_bot_patch_0"] = LE_bot_patch[0]
        temp_fin_patch_dict["LE_bot_patch_1"] = LE_bot_patch[1]

        if self.verbosity > 1:
            print("    Adding bottom face.")

        thickness_top = fin_thickness_function_top(x=p3.x, y=p3.y).z
        thickness_bot = fin_thickness_function_bot(x=p3.x, y=p3.y).z
        elipse_top = ElipsePath(
            centre=p3,
            thickness=thickness_top,
            LE_width=leading_edge_width_function(1),
            side="top",
        )
        elipse_bot = ElipsePath(
            centre=p3,
            thickness=thickness_bot,
            LE_width=leading_edge_width_function(1),
            side="bot",
        )
        elipse_top = ArcLengthParameterizedPath(underlying_path=elipse_top)
        elipse_bot = ArcLengthParameterizedPath(underlying_path=elipse_bot)

        p3p3_top = Line(p0=p3 - Vector3(0, 0, fin_thickness / 2), p1=p3)
        p3p3_bot = Line(p0=p3, p1=p3 + Vector3(0, 0, fin_thickness / 2))

        temp_bottom_ellipse_patch = CoonsPatch(
            north=p3p3_bot, south=elipse_top, east=elipse_bot, west=p3p3_top
        )

        # Rotate patch into x-z plane about p3
        bottom_ellipse_patch = RotatedPatch(
            temp_bottom_ellipse_patch, np.deg2rad(-90), axis="z", point=p3
        )

        # Create rectangular patches for rest of fin bottom
        p3p0 = Line(p3, p0)
        p3p0_bot = Line(
            p0=p3 + Vector3(0, 0, fin_thickness / 2),
            p1=p0 + Vector3(0, 0, fin_thickness / 2),
        )
        p3p0_top = Line(
            p0=p3 - Vector3(0, 0, fin_thickness / 2),
            p1=p0 - Vector3(0, 0, fin_thickness / 2),
        )

        p0p0_top = Line(p0=p0, p1=p0 - Vector3(0, 0, fin_thickness / 2))
        p0_botp0 = Line(p0=p0 + Vector3(0, 0, fin_thickness / 2), p1=p0)
        p3p3_top = Line(p0=p3, p1=p3 - Vector3(0, 0, fin_thickness / 2))
        p3_botp3 = Line(p0=p3 + Vector3(0, 0, fin_thickness / 2), p1=p3)

        bot_1 = CoonsPatch(north=p3p0_top, south=p3p0, east=p0p0_top, west=p3p3_top)
        bot_2 = CoonsPatch(north=p3p0, south=p3p0_bot, east=p0_botp0, west=p3_botp3)

        temp_fin_patch_dict["bot_ellip"] = bottom_ellipse_patch
        temp_fin_patch_dict["bot_1"] = bot_1
        temp_fin_patch_dict["bot_2"] = bot_2

        if self.verbosity > 1:
            print("    Adding Trailing Edge.")

        if self.params["rudder_type"] == "sharp":
            # Create sharp trailing edge

            # First create top and bottom paths connecting fin to TE
            TE_top = TrailingEdgePath(
                p0, p1, thickness_function=fin_thickness_function_top
            )
            TE_bot = TrailingEdgePath(
                p0, p1, thickness_function=fin_thickness_function_bot
            )

            # Make top and bottom of rudder
            TE_top_patch = TrailingEdgePatch(
                A0=p0,
                B0=p1,
                TE_path=TE_top,
                flap_length=self.params["rudder_length"],
                flap_angle=self.params["rudder_angle"],
                side="top",
            )
            TE_bot_patch = TrailingEdgePatch(
                A0=p0,
                B0=p1,
                TE_path=TE_bot,
                flap_length=self.params["rudder_length"],
                flap_angle=self.params["rudder_angle"],
                side="bot",
            )

            # Create corner patches
            thickness_top = fin_thickness_function_top(x=p1.x, y=p1.y).z
            thickness_bot = fin_thickness_function_bot(x=p1.x, y=p1.y).z

            elipse_top = ElipsePath(
                centre=p1,
                thickness=thickness_top,
                LE_width=leading_edge_width_function(0.0),
                side="top",
            )
            elipse_bot = ElipsePath(
                centre=p1,
                thickness=thickness_bot,
                LE_width=leading_edge_width_function(0.0),
                side="bot",
            )
            elipse_top = ArcLengthParameterizedPath(underlying_path=elipse_top)
            elipse_bot = ArcLengthParameterizedPath(underlying_path=elipse_bot)

            south = Line(
                p0=Vector3(x=p1.x, y=p1.y, z=thickness_top),
                p1=Vector3(
                    x=p1.x - self.params["rudder_length"],
                    y=p1.y,
                    z=self.params["rudder_length"]
                    * np.sin(self.params["rudder_angle"]),
                ),
            )
            east = Line(
                p0=Vector3(
                    x=p1.x - self.params["rudder_length"],
                    y=p1.y,
                    z=self.params["rudder_length"]
                    * np.sin(self.params["rudder_angle"]),
                ),
                p1=Vector3(x=p1.x, y=p1.y, z=thickness_bot),
            )

            TE_ellip_patch = CoonsPatch(
                north=elipse_bot, west=elipse_top, south=south, east=east
            )

            # Create bottom triangle patch
            p0_top = p0 - Vector3(0, 0, fin_thickness / 2)
            p0_bot = p0 + Vector3(0, 0, fin_thickness / 2)
            TE = Vector3(
                x=p0.x - self.params["rudder_length"],
                y=p0.y,
                z=self.params["rudder_length"] * np.sin(self.params["rudder_angle"]),
            )

            p0p0_top = Line(p0=p0 - Vector3(0, 0, fin_thickness / 2), p1=p0)
            p0p0_bot = Line(p0=p0, p1=p0 + Vector3(0, 0, fin_thickness / 2))
            p0_top_TE = Line(p0=p0_top, p1=TE)
            p0_bot_TE = Line(p0=TE, p1=p0_bot)

            TE_triangle_patch = CoonsPatch(
                north=p0_bot_TE, south=p0p0_top, east=p0p0_bot, west=p0_top_TE
            )

            # Add to patch dict
            temp_fin_patch_dict["TE_top"] = TE_top_patch
            temp_fin_patch_dict["TE_bot"] = TE_bot_patch
            temp_fin_patch_dict["TE_ellipse"] = TE_ellip_patch
            temp_fin_patch_dict["TE_triangle"] = TE_triangle_patch

        else:
            # Create patch for top of fin TE (elliptical section)
            thickness_top = fin_thickness_function_top(x=p1.x, y=p1.y).z
            thickness_bot = fin_thickness_function_bot(x=p1.x, y=p1.y).z
            elipse_top = ElipsePath(
                centre=p1,
                thickness=thickness_top,
                LE_width=leading_edge_width_function(0.0),
                side="top",
            )
            elipse_bot = ElipsePath(
                centre=p1,
                thickness=thickness_bot,
                LE_width=leading_edge_width_function(0.0),
                side="bot",
            )
            elipse_top = ArcLengthParameterizedPath(underlying_path=elipse_top)
            elipse_bot = ArcLengthParameterizedPath(underlying_path=elipse_bot)

            # Now reverse the paths for correct orientation
            elipse_top = SubRangedPath(underlying_path=elipse_top, t0=1.0, t1=0.0)
            elipse_bot = SubRangedPath(underlying_path=elipse_bot, t0=1.0, t1=0.0)

            p1p1_top = Line(p0=p1, p1=p1 - Vector3(0, 0, fin_thickness / 2))
            p1_botp1 = Line(p0=p1 + Vector3(0, 0, fin_thickness / 2), p1=p1)

            back_ellipse_patch = CoonsPatch(
                north=p1p1_top, south=elipse_bot, east=elipse_top, west=p1_botp1
            )

            # Create rectangular patches for rest of fin TE
            p0_botp1_bot = Line(
                p0=p0 + Vector3(0, 0, fin_thickness / 2),
                p1=p1 + Vector3(0, 0, fin_thickness / 2),
            )
            p0_top1_top = Line(
                p0=p0 - Vector3(0, 0, fin_thickness / 2),
                p1=p1 - Vector3(0, 0, fin_thickness / 2),
            )

            p0p0_top = Line(p0=p0, p1=p0 - Vector3(0, 0, fin_thickness / 2))
            p0_botp0 = Line(p0=p0 + Vector3(0, 0, fin_thickness / 2), p1=p0)

            TE_back_1 = CoonsPatch(
                north=p0_top1_top, south=p0p1, east=p1p1_top, west=p0p0_top
            )
            TE_back_2 = CoonsPatch(
                north=p0p1, south=p0_botp1_bot, east=p1_botp1, west=p0_botp0
            )

            # Add to patch dict
            temp_fin_patch_dict["TE_ellip"] = back_ellipse_patch
            temp_fin_patch_dict["TE_1"] = TE_back_1
            temp_fin_patch_dict["TE_2"] = TE_back_2

        # Create fin patch dict
        fin_patch_dict = temp_fin_patch_dict.copy()

        # Rotate patches again for rudder angle
        if "pivot_angle" in self.params:
            for key, patch in fin_patch_dict.items():
                fin_patch_dict[key] = RotatedPatch(
                    patch,
                    self.params["pivot_angle"],
                    axis="y",
                    point=self.params["pivot_point"],
                )

        # Rotate patches and add to fin_patch_dict
        for key, patch in fin_patch_dict.items():
            fin_patch_dict[key] = RotatedPatch(patch, fin_angle)

        if (
            "offset_function" in self.params
            and self.params["offset_function"] is not None
        ):
            if self.verbosity > 1:
                print("    Applying fin offset function.")
            for patch in fin_patch_dict:
                fin_patch_dict[patch] = OffsetPatchFunction(
                    fin_patch_dict[patch], self.params["offset_function"]
                )
